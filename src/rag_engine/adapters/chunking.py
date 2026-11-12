"""구조 우선 청킹 전략(명세 "청킹과 토큰 세기", ADR 0010).

파서가 준 블록을 순서대로 걸으며 제목 블록으로 절 경로를 유지하고, 같은 절의 블록을 모아 임베딩에
보내는 글(`compose_index_text`)이 상한을 넘는 지점에서 조각을 닫는다. 규칙 일곱은 명세의 번호
그대로다. 넘치는 블록은 문장 경계(kiwipiepy)에서, 넘치는 문장은 토큰 경계에서, 넘치는 표는 행에서
나눈다. 규칙을 바꾸면 `STRUCTURE_FIRST_VERSION`을 올린다. 판이 청킹 해시에 들어 그 구현이 바뀐
코드가 도는 설치에서 "재색인 필요"로 드러난다(`index_elements`).

토큰 수는 단위(블록, 문장, 표 행 묶음)마다 한 번에 세어 어림으로 채우고, 조각을 닫기 전에 실제 글
전체의 토큰 수에 특수 토큰 수를 더해 상한 안인지 다시 잰다. 토크나이저는 글을 이으면 토큰 수가
달라질 수 있어 따로 센 값의 합은 어림일 뿐이다. 넘으면 뒤 단위를 덜어 내고, 단위 하나가 겹침 없이도
넘으면 그 단위를 토큰 경계에서 반으로 나눈다. 규칙 여섯(절의 마지막 조각 합치기)은 어림이 실제보다
컸을 때 남는 작은 조각을 거둔다.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum, auto
from math import ceil
from typing import Final

from rag_engine.adapters.index_elements import STRUCTURE_FIRST_VERSION
from rag_engine.adapters.kiwi import split_sentences
from rag_engine.domain.entities import Block, BlockKind, ChunkDraft, ChunkingConfig, ChunkLocation
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.index_text import (
    compose_index_text,
    fit_section,
    section_candidates,
    section_line,
    section_token_limit,
)
from rag_engine.domain.ports import Chunker, TokenMeter

STRATEGY_NAME: Final = "structure_first"

# 같은 블록을 나눈 조각과 문장을 잇는 구분자, 블록을 잇는 구분자, 목록 항목을 잇는 구분자.
_PIECE_JOINER: Final = " "
_BLOCK_JOINER: Final = "\n\n"
_LIST_JOINER: Final = "\n"

# 절의 마지막 조각이 상한의 10% 아래면 앞 조각에 합친다(규칙 여섯).
_TAIL_SHARE: Final = 10


@dataclass(frozen=True, slots=True)
class _Item:
    """절 안의 본문 블록 하나. 글은 앞뒤 공백을 뗀 것이다."""

    block: Block
    text: str
    tokens: int


@dataclass(frozen=True, slots=True)
class _Section:
    path: tuple[str, ...]
    items: tuple[_Item, ...]


class _Form(Enum):
    """단위가 어떻게 나왔는지. 나누기와 합치기와 겹침이 이 값으로 갈린다."""

    BLOCK = auto()  # 블록 하나를 그대로 담았다. 문장으로 더 나눌 수 있다.
    PIECE = auto()  # 문장 하나이거나 토큰 경계로 자른 조각이다. 더 나누지 않는다.
    TABLE_PIECE = auto()  # 표를 행으로 나눈 조각이다. 다른 단위와 합치지 않고 조각 하나가 된다.


@dataclass(frozen=True, slots=True)
class _Unit:
    """조각에 담는 글의 최소 단위. 블록 하나, 나뉜 문장, 토큰 경계로 자른 조각, 표 행 묶음이다.

    `joiner`는 앞 단위와 이을 때 쓴다.
    """

    text: str
    ordinal: int
    page: int | None
    kind: BlockKind
    joiner: str
    tokens: int
    form: _Form = _Form.BLOCK

    @property
    def standalone(self) -> bool:
        return self.form is _Form.TABLE_PIECE

    @property
    def atomic(self) -> bool:
        return self.form is not _Form.BLOCK


@dataclass(frozen=True, slots=True)
class _Draft:
    """닫은 조각. `overlap`은 앞 조각에서 가져온 끝 문장이고 `own`은 이 조각이 새로 맡은 단위다."""

    overlap: tuple[_Unit, ...]
    own: tuple[_Unit, ...]
    text: str
    total: int


@dataclass(frozen=True, slots=True)
class _SectionPath:
    """절의 경로. `trimmed`가 상한의 4분의 1 안으로 줄인 것이고 `base`는 본문 앞에 드는 토큰 수다
    (특수 토큰, 절 경로 줄, 빈 줄)."""

    full: tuple[str, ...]
    trimmed: tuple[str, ...]
    base: int


class StructureFirstChunker:
    """`Chunker` 포트의 구조 우선 전략."""

    version: Final = STRUCTURE_FIRST_VERSION

    async def chunk(
        self, blocks: Sequence[Block], config: ChunkingConfig, tokens: TokenMeter
    ) -> list[ChunkDraft]:
        if config.strategy != STRATEGY_NAME:
            raise ConfigurationError(f"구조 우선 전략이 아닌 이름이다: {config.strategy}")
        joiners = [_BLOCK_JOINER, _LIST_JOINER, _PIECE_JOINER]
        joiner_tokens = await tokens.count_tokens(joiners)
        run = _ChunkingRun(
            config=config,
            tokens=tokens,
            special=await tokens.special_token_count(),
            joiner_cost=dict(zip(joiners, joiner_tokens, strict=True)),
        )
        return await run.chunk(blocks)


class _ChunkingRun:
    """청킹 한 번의 상태. 설정, 토큰 세기, 특수 토큰 수, 구분자의 토큰 수를 든다."""

    def __init__(
        self,
        *,
        config: ChunkingConfig,
        tokens: TokenMeter,
        special: int,
        joiner_cost: Mapping[str, int],
    ) -> None:
        self._max_tokens = config.max_tokens
        self._overlap_tokens = config.overlap_tokens
        self._tokens = tokens
        self._special = special
        self._joiner_cost = joiner_cost

    async def chunk(self, blocks: Sequence[Block]) -> list[ChunkDraft]:
        texts = [block.text.strip() for block in blocks]
        counts = await self._tokens.count_tokens(texts)
        sections = self._sections(blocks, texts, counts)
        path_tokens = await self._path_tokens(sections)
        chunks: list[ChunkDraft] = []
        for section in sections:
            path = self._fit_path(section.path, path_tokens)
            drafts = await self._chunk_section(section, path)
            chunks.extend(self._chunk_draft(draft, path) for draft in drafts)
        return chunks

    def _sections(
        self, blocks: Sequence[Block], texts: Sequence[str], counts: Sequence[int]
    ) -> list[_Section]:
        """제목 블록으로 절을 가른다. 글 하나가 상한의 4분의 1을 넘는 제목 블록은 제목으로 보지 않고
        문단 블록으로 본문에 둔다(규칙 일곱)."""
        limit = section_token_limit(self._max_tokens)
        sections: list[_Section] = []
        stack: list[tuple[int, str]] = []
        path: tuple[str, ...] = ()
        items: list[_Item] = []
        for block, text, tokens in zip(blocks, texts, counts, strict=True):
            if not text:
                continue
            if block.kind is BlockKind.HEADING and block.level is not None and tokens <= limit:
                if items:
                    sections.append(_Section(path, tuple(items)))
                    items = []
                while stack and stack[-1][0] >= block.level:
                    stack.pop()
                stack.append((block.level, text))
                path = tuple(title for _, title in stack)
                continue
            kind = BlockKind.PARAGRAPH if block.kind is BlockKind.HEADING else block.kind
            items.append(_Item(replace(block, kind=kind, level=None), text, tokens))
        if items:
            sections.append(_Section(path, tuple(items)))
        return sections

    async def _path_tokens(self, sections: Sequence[_Section]) -> dict[str, int]:
        """모든 절의 절 경로 후보 줄을 한 번에 세어 둔다."""
        lines = {line for section in sections for line in section_candidates(section.path)}
        ordered = sorted(lines)
        counts = await self._tokens.count_tokens(ordered)
        return dict(zip(ordered, counts, strict=True))

    def _fit_path(self, full: tuple[str, ...], path_tokens: Mapping[str, int]) -> _SectionPath:
        """절 경로 줄을 상한 안으로 줄인다(`fit_section`)."""
        if not full:
            return _SectionPath(full, (), self._special)
        trimmed = fit_section(full, self._max_tokens, path_tokens)
        return _SectionPath(
            full,
            trimmed,
            self._special + path_tokens[section_line(trimmed)] + self._joiner_cost[_BLOCK_JOINER],
        )

    async def _chunk_section(self, section: _Section, path: _SectionPath) -> list[_Draft]:
        budget = self._max_tokens - path.base
        if budget < 1:
            raise ConfigurationError("조각 상한이 특수 토큰과 절 경로 줄을 담기에 너무 작다")
        units = await self._units(section.items, budget)
        drafts = await self._pack(units, path)
        return await self._merge_last(drafts, path)

    # 단위 만들기: 상한 안의 블록은 그대로, 넘는 블록은 문장과 토큰 경계와 표 행으로 나눈다.

    async def _units(self, items: Sequence[_Item], budget: int) -> list[_Unit]:
        units: list[_Unit] = []
        previous: BlockKind | None = None
        for item in items:
            kind = item.block.kind
            joiner = _LIST_JOINER if kind is BlockKind.LIST_ITEM is previous else _BLOCK_JOINER
            previous = kind
            if item.tokens <= budget:
                units.append(self._block_unit(item, joiner))
            elif kind is BlockKind.TABLE and "\n" in item.text:
                units.extend(await self._split_table(item, joiner, budget))
            else:
                units.extend(await self._split_text(item, joiner, budget))
        return units

    def _block_unit(self, item: _Item, joiner: str) -> _Unit:
        block = item.block
        return _Unit(item.text, block.ordinal, block.page, block.kind, joiner, item.tokens)

    async def _split_text(self, item: _Item, joiner: str, budget: int) -> list[_Unit]:
        """문장 경계에서 나누고, 문장 하나가 넘으면 그 문장을 토큰 경계에서 고르게 나눈다."""
        sentences = split_sentences(item.text) or [item.text]
        counts = await self._tokens.count_tokens(sentences)
        units: list[_Unit] = []
        for sentence, tokens in zip(sentences, counts, strict=True):
            first_joiner = joiner if not units else _PIECE_JOINER
            if tokens <= budget:
                units.append(self._piece(item, sentence, tokens, first_joiner))
                continue
            pieces = await self._token_pieces(sentence, ceil(tokens / budget))
            piece_counts = await self._tokens.count_tokens(pieces)
            for index, (piece, piece_tokens) in enumerate(zip(pieces, piece_counts, strict=True)):
                piece_joiner = first_joiner if index == 0 else _PIECE_JOINER
                units.append(self._piece(item, piece, piece_tokens, piece_joiner))
        return units

    def _piece(self, item: _Item, text: str, tokens: int, joiner: str) -> _Unit:
        block = item.block
        return _Unit(text, block.ordinal, block.page, block.kind, joiner, tokens, _Form.PIECE)

    async def _split_table(self, item: _Item, joiner: str, budget: int) -> list[_Unit]:
        """표를 행 단위로 나누고 조각마다 머리 행을 되풀이한다. 머리 행과 함께 상한에 들지 않는
        행은 토큰 경계에서 나누고, 그 조각은 머리 행 없이 행 글만 담는다(머리 행을 붙일 자리가
        없다). 어느 조각에도 머리 행이 들지 못했으면 머리 행만 담은 조각을 맨 앞에 둔다(열 이름이
        색인에서 사라지지 않게 한다). 표를 나눈 조각은 다른 단위와 합치지 않는다."""
        lines = [line for line in item.text.split("\n") if line.strip()]
        header, rows = lines[0], lines[1:]
        header_tokens, *row_tokens = await self._tokens.count_tokens([header, *rows])
        newline = self._joiner_cost[_LIST_JOINER]
        units: list[_Unit] = []
        group: list[str] = []
        group_tokens = header_tokens
        header_placed = False

        def flush() -> None:
            nonlocal group, group_tokens, header_placed
            if group:
                text = "\n".join([header, *group])
                units.append(self._table_unit(item, text, group_tokens, joiner))
                header_placed = True
            group, group_tokens = [], header_tokens

        for row, tokens in zip(rows, row_tokens, strict=True):
            if header_tokens + newline + tokens > budget:
                flush()
                pieces = await self._token_pieces(row, ceil(tokens / budget))
                piece_counts = await self._tokens.count_tokens(pieces)
                units.extend(
                    self._table_unit(item, piece, count, joiner)
                    for piece, count in zip(pieces, piece_counts, strict=True)
                )
                continue
            if group_tokens + newline + tokens > budget:
                flush()
            group.append(row)
            group_tokens += newline + tokens
        flush()
        if not header_placed:
            units.insert(0, self._table_unit(item, header, header_tokens, joiner))
        return units

    def _table_unit(self, item: _Item, text: str, tokens: int, joiner: str) -> _Unit:
        block = item.block
        return _Unit(text, block.ordinal, block.page, block.kind, joiner, tokens, _Form.TABLE_PIECE)

    async def _token_pieces(self, text: str, parts: int) -> list[str]:
        """글을 토큰 경계에서 `parts`개로 고르게 나눈다. 토큰이 둘보다 적으면 나누지 못한다."""
        spans = await self._tokens.token_spans(text)
        if len(spans) < 2:
            return [text]
        capacity = ceil(len(spans) / parts)
        groups = [spans[start : start + capacity] for start in range(0, len(spans), capacity)]
        return [text[group[0][0] : group[-1][1]] for group in groups]

    async def _halve(self, unit: _Unit) -> list[_Unit]:
        pieces = await self._token_pieces(unit.text, 2)
        if len(pieces) < 2:
            raise ConfigurationError("조각 상한이 너무 작아 글 하나를 담을 수 없다")
        counts = await self._tokens.count_tokens(pieces)
        later_joiner = unit.joiner if unit.standalone else _PIECE_JOINER
        form = _Form.TABLE_PIECE if unit.standalone else _Form.PIECE
        return [
            replace(
                unit,
                text=piece,
                tokens=count,
                joiner=unit.joiner if index == 0 else later_joiner,
                form=form,
            )
            for index, (piece, count) in enumerate(zip(pieces, counts, strict=True))
        ]

    # 조각 닫기: 어림으로 채우고 실제 글 전체로 상한을 확인한다.

    async def _pack(self, given: Sequence[_Unit], path: _SectionPath) -> list[_Draft]:
        units = list(given)  # 상한을 넘는 단위를 반으로 갈라 끼우므로 인자가 아니라 사본을 바꾼다.
        drafts: list[_Draft] = []
        index = 0
        overlap: tuple[_Unit, ...] = ()
        while index < len(units):
            unit = units[index]
            if unit.standalone:
                taken, carried = (unit,), ()
            else:
                taken, carried = self._take_by_estimate(units, index, overlap, path.base)
            draft = await self._seal(taken, carried, path)
            if draft is None:
                units[index : index + 1] = await self._halve(unit)
                continue
            drafts.append(draft)
            index += len(draft.own)
            overlap = await self._overlap_of(draft.own)
        return drafts

    def _take_by_estimate(
        self, units: Sequence[_Unit], index: int, overlap: tuple[_Unit, ...], base: int
    ) -> tuple[tuple[_Unit, ...], tuple[_Unit, ...]]:
        """따로 센 토큰 수의 합으로 상한까지 단위를 채운다. 겹침과 함께 하나도 들지 않으면 겹침을
        버리고, 그래도 들지 않으면 단위 하나를 그대로 내어 실제 글로 재게 한다."""
        while True:
            running = base + self._estimated(overlap)
            taken: list[_Unit] = []
            for unit in units[index:]:
                if unit.standalone:
                    break
                joiner = self._joiner_cost[unit.joiner] if overlap or taken else 0
                if running + unit.tokens + joiner > self._max_tokens:
                    break
                taken.append(unit)
                running += unit.tokens + joiner
            if taken:
                return tuple(taken), overlap
            if overlap:
                overlap = ()
                continue
            return (units[index],), overlap

    def _estimated(self, units: Sequence[_Unit]) -> int:
        joiners = sum(self._joiner_cost[unit.joiner] for unit in units[1:])
        return sum(unit.tokens for unit in units) + joiners

    async def _seal(
        self, taken: tuple[_Unit, ...], carried: tuple[_Unit, ...], path: _SectionPath
    ) -> _Draft | None:
        """실제 글 전체의 토큰 수가 상한 안이 될 때까지 뒤 단위를 덜고 겹침(`carried`)을 버린다.
        단위 하나로도 넘으면 `None`이다."""
        while True:
            text = _join([*carried, *taken])
            total = await self._total(compose_index_text(path.trimmed, text))
            if total <= self._max_tokens:
                return _Draft(carried, taken, text, total)
            if len(taken) > 1:
                taken = taken[:-1]
            elif carried:
                carried = ()
            else:
                return None

    async def _total(self, index_text: str) -> int:
        (tokens,) = await self._tokens.count_tokens([index_text])
        return tokens + self._special

    async def _overlap_of(self, taken: tuple[_Unit, ...]) -> tuple[_Unit, ...]:
        """앞 조각의 끝 문장들을 겹침 토큰 수 안에서 통째로 가져온다. 표에서는 가져오지 않는다."""
        budget = self._overlap_tokens
        tail: list[_Unit] = []
        if budget <= 0:
            return ()
        for unit in reversed(taken):
            if unit.kind is BlockKind.TABLE:
                break
            for sentence in reversed(await self._sentences_of(unit)):
                cost = sentence.tokens + (self._joiner_cost[_PIECE_JOINER] if tail else 0)
                if cost > budget:
                    return tuple(tail)
                tail.insert(0, sentence)
                budget -= cost
        return tuple(tail)

    async def _sentences_of(self, unit: _Unit) -> list[_Unit]:
        if unit.atomic:
            return [unit]
        sentences = split_sentences(unit.text)
        if len(sentences) < 2:
            return [replace(unit, form=_Form.PIECE)]
        counts = await self._tokens.count_tokens(sentences)
        return [
            replace(
                unit,
                text=sentence,
                tokens=count,
                joiner=unit.joiner if index == 0 else _PIECE_JOINER,
                form=_Form.PIECE,
            )
            for index, (sentence, count) in enumerate(zip(sentences, counts, strict=True))
        ]

    async def _merge_last(self, drafts: list[_Draft], path: _SectionPath) -> list[_Draft]:
        """절의 마지막 조각이 상한의 10% 아래이고 앞 조각과 합쳐도 상한 안이면 합친다(규칙 여섯)."""
        if len(drafts) < 2:
            return drafts
        previous, last = drafts[-2], drafts[-1]
        if any(unit.standalone for unit in (*previous.own, *last.own)):
            return drafts
        if self._estimated(last.own) * _TAIL_SHARE >= self._max_tokens:
            return drafts
        own = (*previous.own, *last.own)
        text = _join([*previous.overlap, *own])
        total = await self._total(compose_index_text(path.trimmed, text))
        if total > self._max_tokens:
            return drafts
        return [*drafts[:-2], _Draft(previous.overlap, own, text, total)]

    def _chunk_draft(self, draft: _Draft, path: _SectionPath) -> ChunkDraft:
        covered = [*draft.overlap, *draft.own]
        ordinals = [unit.ordinal for unit in covered]
        return ChunkDraft(
            text=draft.text,
            index_text=compose_index_text(path.trimmed, draft.text),
            token_count=draft.total,
            location=ChunkLocation(
                page=covered[0].page,
                section=path.full,
                block_kind=covered[0].kind,
                block_range=(min(ordinals), max(ordinals)),
            ),
        )


def _join(units: Sequence[_Unit]) -> str:
    text = units[0].text
    for unit in units[1:]:
        text += unit.joiner + unit.text
    return text


# 지식베이스 설정의 전략 이름으로 저장소 안의 구현을 고른다(ADR 0010). 이름을 더하면
# `index_elements`의 전략 판 조회도 같이 더한다.
STRATEGIES: Final[Mapping[str, Callable[[], Chunker]]] = {STRATEGY_NAME: StructureFirstChunker}


def chunker_for(strategy: str) -> Chunker:
    factory = STRATEGIES.get(strategy)
    if factory is None:
        raise ConfigurationError(f"모르는 청킹 전략이다: {strategy}")
    return factory()
