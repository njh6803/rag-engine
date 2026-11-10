"""구조 우선 청킹 전략(명세 "청킹과 토큰 세기"의 규칙 일곱과 근거 위치).

토큰은 글자 수로 센다(`tests/support/token_meters.py`). 그래서 조각이 어디서 닫히는지 글자 수 셈으로
손으로 따질 수 있다. 문장 분리는 실제 kiwipiepy다.
"""

from collections.abc import Sequence

import pytest
from tests.support.token_meters import CharMeter, RoundingUpMeter, ShrinkingMeter

from rag_engine.adapters.chunking import STRATEGIES, StructureFirstChunker, chunker_for
from rag_engine.adapters.index_elements import STRUCTURE_FIRST_VERSION, compute_index_elements
from rag_engine.domain.entities import Block, BlockKind, ChunkDraft, ChunkingConfig
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.ports import TokenMeter

type Spec = tuple[str, str] | tuple[str, str, int]

_KINDS = {
    "h1": (BlockKind.HEADING, 1),
    "h2": (BlockKind.HEADING, 2),
    "h3": (BlockKind.HEADING, 3),
    "p": (BlockKind.PARAGRAPH, None),
    "t": (BlockKind.TABLE, None),
    "li": (BlockKind.LIST_ITEM, None),
}


def blocks_of(*specs: Spec) -> list[Block]:
    """("h1", 글), ("p", 글, 쪽 번호) 꼴의 표로 블록 목록을 짓는다. 순번은 0부터 차례로 매긴다."""
    blocks: list[Block] = []
    for ordinal, spec in enumerate(specs):
        kind, level = _KINDS[spec[0]]
        page = spec[2] if len(spec) == 3 else None
        blocks.append(Block(kind=kind, text=spec[1], level=level, page=page, ordinal=ordinal))
    return blocks


def config(max_tokens: int, overlap: int = 0) -> ChunkingConfig:
    return ChunkingConfig(strategy="structure_first", max_tokens=max_tokens, overlap_tokens=overlap)


async def chunk(
    blocks: Sequence[Block],
    max_tokens: int,
    overlap: int = 0,
    meter: TokenMeter | None = None,
) -> list[ChunkDraft]:
    return await StructureFirstChunker().chunk(
        blocks, config(max_tokens, overlap), meter if meter is not None else CharMeter()
    )


SENTENCE = "{} 문장입니다."
FIRST, SECOND, THIRD, FOURTH = (SENTENCE.format(name) for name in ("첫째", "둘째", "셋째", "넷째"))
# 문장 하나가 아홉 글자이고 문장 사이에 공백 하나가 든다.
PARAGRAPH_OF_FOUR = " ".join([FIRST, SECOND, THIRD, FOURTH])


# 규칙 하나: 제목 블록은 조각이 되지 않고 다음 조각의 절 경로가 된다.


async def test_제목_블록은_조각이_되지_않고_다음_조각의_절_경로가_된다() -> None:
    blocks = blocks_of(("h1", "계약"), ("p", "본문"), ("h2", "정의"), ("p", "용어"))

    drafts = await chunk(blocks, 100)

    assert [draft.text for draft in drafts] == ["본문", "용어"]
    assert [draft.index_text for draft in drafts] == ["계약\n\n본문", "계약 > 정의\n\n용어"]
    assert [draft.location.section for draft in drafts] == [("계약",), ("계약", "정의")]


async def test_같은_수준의_다음_제목은_앞_제목을_절_경로에서_밀어낸다() -> None:
    blocks = blocks_of(
        ("h1", "가"),
        ("h2", "나"),
        ("p", "하나"),
        ("h2", "다"),
        ("p", "둘"),
        ("h1", "라"),
        ("p", "셋"),
    )

    drafts = await chunk(blocks, 100)

    assert [draft.location.section for draft in drafts] == [("가", "나"), ("가", "다"), ("라",)]


async def test_절_경로가_비면_절_경로_줄과_빈_줄을_넣지_않는다() -> None:
    drafts = await chunk(blocks_of(("p", "본문")), 100)

    assert drafts[0].index_text == "본문"
    assert drafts[0].location.section == ()


async def test_본문이_없는_제목과_빈_블록은_조각이_되지_않는다() -> None:
    blocks = blocks_of(("h1", "가"), ("h1", "나"), ("p", "  \n "), ("p", ""))

    assert await chunk(blocks, 100) == []
    assert await chunk([], 100) == []


# 규칙 둘: 같은 절의 블록을 모아 다음 블록을 더하면 상한을 넘는 지점에서 조각을 닫는다.


async def test_같은_절의_블록을_모으다_상한을_넘는_지점에서_조각을_닫는다() -> None:
    first, second, third = "가" * 10, "나" * 10, "다" * 10
    blocks = blocks_of(("h1", "H"), ("p", first), ("p", second), ("p", third))

    drafts = await chunk(blocks, 30)

    # 절 경로 줄 "H"와 빈 줄이 3글자라 본문은 27글자다. 둘을 이은 22글자까지 들어가고 셋은 34글자다.
    assert [draft.text for draft in drafts] == [f"{first}\n\n{second}", third]
    assert [draft.token_count for draft in drafts] == [25, 13]
    assert [draft.location.block_range for draft in drafts] == [(1, 2), (3, 3)]


async def test_목록_항목끼리는_줄바꿈_하나로_잇고_다른_블록과는_빈_줄로_잇는다() -> None:
    blocks = blocks_of(("p", "소개"), ("li", "하나"), ("li", "둘"), ("p", "맺음"))

    drafts = await chunk(blocks, 100)

    assert [draft.text for draft in drafts] == ["소개\n\n하나\n둘\n\n맺음"]


# 규칙 셋: 블록 하나가 상한을 넘으면 문장 경계에서 나누고, 문장 하나가 넘으면 토큰 경계에서 나눈다.


async def test_블록_하나가_상한을_넘으면_문장_경계에서_나눈다() -> None:
    drafts = await chunk(blocks_of(("p", PARAGRAPH_OF_FOUR)), 20)

    assert [draft.text for draft in drafts] == [f"{FIRST} {SECOND}", f"{THIRD} {FOURTH}"]
    assert [draft.location.block_range for draft in drafts] == [(0, 0), (0, 0)]


async def test_문장_하나가_상한을_넘으면_토큰_경계에서_고르게_나눈다() -> None:
    sentence = "가나다라마바사아자차" * 4 + "가나다라마"

    drafts = await chunk(blocks_of(("p", sentence)), 20)

    assert [len(draft.text) for draft in drafts] == [15, 15, 15]
    assert "".join(draft.text for draft in drafts) == sentence


async def test_문장_하나가_넘치는_블록도_앞_문장은_문장_경계를_지킨다() -> None:
    long_sentence = "가나다라마바사아자차" * 4 + "가나다라마"
    blocks = blocks_of(("p", f"{FIRST} {long_sentence}"))

    drafts = await chunk(blocks, 20)

    assert drafts[0].text == FIRST
    assert "".join(draft.text for draft in drafts[1:]) == long_sentence


# 규칙 넷: 표 블록은 행 단위로 나누고 나뉜 조각마다 머리 행을 되풀이한다.


async def test_상한_안의_표는_한_조각으로_둔다() -> None:
    table = "이름 | 값\na | 1\nb | 2"

    drafts = await chunk(blocks_of(("t", table)), 100)

    assert [draft.text for draft in drafts] == [table]
    assert drafts[0].location.block_kind is BlockKind.TABLE


async def test_넘치는_표는_행_단위로_나누고_조각마다_머리_행을_되풀이한다() -> None:
    table = "이름 | 값\na | 1\nb | 2\nc | 3\nd | 4"

    drafts = await chunk(blocks_of(("p", "앞"), ("t", table)), 20)

    assert [draft.text for draft in drafts] == [
        "앞",
        "이름 | 값\na | 1\nb | 2",
        "이름 | 값\nc | 3\nd | 4",
    ]
    assert [draft.location.block_kind for draft in drafts[1:]] == [BlockKind.TABLE] * 2
    assert [draft.location.block_range for draft in drafts[1:]] == [(1, 1), (1, 1)]


async def test_나뉜_표_조각은_작은_마지막_조각이어도_앞_조각과_합치지_않는다() -> None:
    # 마지막 조각 "머\n가"(3)는 상한 100의 10% 아래이고 앞 조각(75)과 합쳐도 상한 안이지만,
    # 표 조각은 머리 행을 되풀이하는 독립 조각이라 합치면 표의 모양이 깨진다.
    table = f"머\n{'가' * 75}{'나' * 75}\n가"

    drafts = await chunk(blocks_of(("t", table)), 100)

    assert [draft.text for draft in drafts] == ["가" * 75, "나" * 75, "머\n가"]


async def test_표_조각_뒤의_문단은_표를_겹침으로_가져오지_않는다() -> None:
    table = f"머리\n{'가' * 30}\n{'나' * 30}"

    drafts = await chunk(blocks_of(("t", table), ("p", "다음")), 40, overlap=36)

    assert [draft.text for draft in drafts] == [f"머리\n{'가' * 30}", f"머리\n{'나' * 30}", "다음"]


async def test_머리_행과_한_행이_상한을_넘는_표의_행은_토큰_경계에서_나눈다() -> None:
    long_row = "가나다라마바사아자차카타파하" * 2
    table = f"머리\n{long_row}\n짧음"

    drafts = await chunk(blocks_of(("t", table)), 20)

    assert [draft.text for draft in drafts] == [long_row[:14], long_row[14:], "머리\n짧음"]
    assert all(draft.location.block_kind is BlockKind.TABLE for draft in drafts)


# 규칙 다섯: 겹침은 같은 절 안에서만 두고 앞 조각의 끝 문장들을 겹침 토큰 수 안에서 통째로 가져온다.


async def test_겹침은_앞_조각의_끝_문장을_겹침_토큰_수_안에서_통째로_가져온다() -> None:
    drafts = await chunk(blocks_of(("p", PARAGRAPH_OF_FOUR)), 30, overlap=10)

    assert [draft.text for draft in drafts] == [f"{FIRST} {SECOND} {THIRD}", f"{THIRD} {FOURTH}"]


async def test_겹침_토큰_수가_문장_하나보다_작으면_겹치지_않는다() -> None:
    drafts = await chunk(blocks_of(("p", PARAGRAPH_OF_FOUR)), 30, overlap=8)

    assert [draft.text for draft in drafts] == [f"{FIRST} {SECOND} {THIRD}", FOURTH]


async def test_겹침은_절이_바뀌면_두지_않는다() -> None:
    blocks = blocks_of(("h1", "가"), ("p", PARAGRAPH_OF_FOUR), ("h1", "나"), ("p", "새 절의 본문"))

    drafts = await chunk(blocks, 40, overlap=20)

    assert drafts[-1].text == "새 절의 본문"
    assert drafts[-1].location.section == ("나",)


async def test_겹침_문장도_근거_위치에_들어간다() -> None:
    blocks = blocks_of(("p", PARAGRAPH_OF_FOUR + "\n"), ("p", "다섯째 블록", 7))

    drafts = await chunk(blocks, 30, overlap=10)

    # 둘째 조각은 첫째 블록의 끝 문장(겹침)으로 시작해 둘째 블록까지 덮는다.
    assert drafts[1].text.startswith(THIRD)
    assert drafts[1].location.block_range == (0, 1)
    assert drafts[1].location.page is None


# 규칙 여섯: 절의 마지막 조각이 상한의 10% 아래면 앞 조각에 합친다(합쳐도 상한 안일 때).


async def test_어림이_실제보다_커서_남은_마지막_조각은_합쳐도_상한_안이면_앞_조각에_합친다() -> (
    None
):
    # 이 셈에서는 글자 열 개가 토큰 아홉 개라, 따로 센 값을 더한 어림(38+2+1=41)이 상한 40을 넘어
    # 마지막 블록이 따로 남지만 이어서 센 실제 값(39)은 상한 안이다.
    blocks = blocks_of(("p", "가" * 19), ("p", "나" * 19), ("p", "다"))

    drafts = await chunk(blocks, 40, meter=ShrinkingMeter())

    assert [draft.text for draft in drafts] == ["가" * 19 + "\n\n" + "나" * 19 + "\n\n" + "다"]
    assert drafts[0].token_count == 39


async def test_합치면_상한을_넘는_마지막_조각은_합치지_않는다() -> None:
    blocks = blocks_of(("p", "가" * 20), ("p", "나" * 20), ("p", "다다"))

    drafts = await chunk(blocks, 45)

    assert [draft.text for draft in drafts] == ["가" * 20 + "\n\n" + "나" * 20, "다다"]


async def test_상한의_10퍼센트_이상인_마지막_조각은_합치지_않는다() -> None:
    blocks = blocks_of(("p", "가" * 19), ("p", "나" * 19), ("p", "다" * 4))

    drafts = await chunk(blocks, 40, meter=ShrinkingMeter())

    assert len(drafts) == 2


# 규칙 일곱: 절 경로 줄은 상한의 4분의 1 안이다.


async def test_절_경로가_상한의_4분의_1을_넘으면_바깥_제목부터_뺀다() -> None:
    outer, middle, inner = "가" * 10, "나" * 10, "다" * 10
    blocks = blocks_of(("h1", outer), ("h2", middle), ("h3", inner), ("p", "본문"))

    drafts = await chunk(blocks, 80)

    # 80의 4분의 1은 20이다. 세 제목을 이으면 36, 둘이면 23이라 안쪽 제목 하나만 남는다.
    assert drafts[0].index_text == f"{inner}\n\n본문"
    assert drafts[0].location.section == (outer, middle, inner)


async def test_절_경로가_상한의_4분의_1_안이면_줄이지_않는다() -> None:
    blocks = blocks_of(("h1", "가" * 8), ("h2", "나" * 8), ("p", "본문"))

    drafts = await chunk(blocks, 80)

    assert drafts[0].index_text == f"{'가' * 8} > {'나' * 8}\n\n본문"


async def test_제목_블록이_상한의_4분의_1과_꼭_같으면_제목으로_다룬다() -> None:
    title = "가" * 20
    blocks = blocks_of(("h1", title), ("p", "본문"))

    drafts = await chunk(blocks, 80)

    assert [draft.text for draft in drafts] == ["본문"]
    assert drafts[0].location.section == (title,)


async def test_제목_블록_하나가_상한의_4분의_1을_넘으면_제목이_아니라_문단으로_다룬다() -> None:
    long_title = "가" * 30
    blocks = blocks_of(("h1", "H"), ("h2", long_title), ("p", "본문"))

    drafts = await chunk(blocks, 80)

    assert [draft.text for draft in drafts] == [f"{long_title}\n\n본문"]
    assert drafts[0].location.section == ("H",)
    assert drafts[0].location.block_kind is BlockKind.PARAGRAPH
    assert drafts[0].location.block_range == (1, 2)


async def test_절_경로에_들지_못한_긴_제목은_뒤의_절_경로에도_끼지_않는다() -> None:
    blocks = blocks_of(("h1", "가" * 30), ("p", "본문"), ("h2", "나"), ("p", "다음"))

    drafts = await chunk(blocks, 80)

    assert [(draft.text, draft.location.section) for draft in drafts] == [
        ("가" * 30 + "\n\n본문", ()),
        ("다음", ("나",)),
    ]


@pytest.mark.parametrize("max_tokens", [40, 60, 100])
async def test_어떤_조각도_절_경로만으로_상한을_넘지_않는다(max_tokens: int) -> None:
    titles = [("h1", "가" * 18), ("h2", "나" * 18), ("h3", "다" * 18)]
    blocks = blocks_of(*titles, ("p", "라" * 200))

    drafts = await chunk(blocks, max_tokens)

    assert drafts
    assert all(draft.token_count <= max_tokens for draft in drafts)
    assert all(len(draft.index_text) <= max_tokens for draft in drafts)


# 근거 위치와 토큰 수.


async def test_근거_위치는_첫_블록의_쪽과_종류와_덮은_블록_순번의_처음과_끝이다() -> None:
    blocks = blocks_of(
        ("h1", "가"),
        ("p", "하나", 3),
        ("li", "둘", 4),
        ("p", "셋", 4),
        ("h1", "나"),
        ("p", "넷", 5),
    )

    drafts = await chunk(blocks, 100)

    first, second = drafts
    assert first.location.page == 3
    assert first.location.block_kind is BlockKind.PARAGRAPH
    assert first.location.block_range == (1, 3)
    assert second.location.page == 5
    assert second.location.block_range == (5, 5)


async def test_쪽이_없는_블록의_조각은_쪽이_없다() -> None:
    drafts = await chunk(blocks_of(("p", "본문")), 100)

    assert drafts[0].location.page is None


async def test_상한은_글의_토큰_수에_특수_토큰_수를_더해_잰다() -> None:
    fits = "가" * 28
    over = "가" * 29

    fitting = await chunk(blocks_of(("p", fits)), 30, meter=CharMeter(special=2))
    overflowing = await chunk(blocks_of(("p", over)), 30, meter=CharMeter(special=2))

    assert [draft.text for draft in fitting] == [fits]
    assert fitting[0].token_count == 30
    assert len(overflowing) == 2
    assert all(draft.token_count <= 30 for draft in overflowing)


async def test_상한은_절_경로_줄까지_더한_글_전체로_잰다() -> None:
    blocks = blocks_of(("h1", "절"), ("p", "가" * 26))

    drafts = await chunk(blocks, 30)

    # 절 경로 줄 "절"과 빈 줄이 3글자라 26글자 본문은 29글자가 되어 상한 30 안이다. 28글자면 넘는다.
    assert len(drafts) == 1
    assert drafts[0].token_count == 29
    assert len(await chunk(blocks_of(("h1", "절"), ("p", "가" * 28)), 30)) == 2


@pytest.mark.parametrize(
    "meter",
    [CharMeter(), RoundingUpMeter(), ShrinkingMeter(special=2)],
    ids=["가산", "올림", "내림"],
)
async def test_토큰_수가_더해지지_않는_세기에서도_어떤_조각도_상한을_넘지_않는다(
    meter: TokenMeter,
) -> None:
    blocks = blocks_of(
        ("h1", "제3조 정의"),
        ("p", PARAGRAPH_OF_FOUR + "\n" + PARAGRAPH_OF_FOUR),
        ("p", "가" * 70),
        ("t", "이름 | 값\n" + "\n".join(f"행{i} | {i * 111}" for i in range(12))),
        ("li", "목록 하나"),
        ("li", "목록 둘"),
        ("h2", "나"),
        ("p", PARAGRAPH_OF_FOUR),
    )

    drafts = await chunk(blocks, 60, overlap=12, meter=meter)

    assert len(drafts) > 4
    counts = await meter.count_tokens([draft.index_text for draft in drafts])
    special = await meter.special_token_count()
    assert [count + special for count in counts] == [draft.token_count for draft in drafts]
    assert all(draft.token_count <= 60 for draft in drafts)


async def test_겹침이_없으면_조각_글을_이어_붙인_것이_본문과_같다() -> None:
    body = [PARAGRAPH_OF_FOUR, "가" * 70, "마지막 블록"]
    blocks = blocks_of(("h1", "절"), *(("p", text) for text in body))

    drafts = await chunk(blocks, 40)

    squeezed = "".join("".join(draft.text.split()) for draft in drafts)
    assert squeezed == "".join("".join(text.split()) for text in body)


async def test_같은_입력은_같은_조각을_낸다() -> None:
    blocks = blocks_of(("h1", "절"), ("p", PARAGRAPH_OF_FOUR), ("t", "머리\n가 | 1\n나 | 2"))

    assert await chunk(blocks, 25, overlap=10) == await chunk(blocks, 25, overlap=10)


async def test_상한이_절_경로와_특수_토큰을_담기에_너무_작으면_설정_오류다() -> None:
    blocks = blocks_of(("h1", "가"), ("p", "본문"))

    # 특수 토큰 7개와 절 경로 줄 "가"와 빈 줄 2글자가 상한 8을 넘어 본문이 들어갈 자리가 없다.
    with pytest.raises(ConfigurationError, match="특수 토큰과 절 경로 줄을 담기에 너무 작다"):
        await chunk(blocks, 8, meter=CharMeter(special=7))


# 전략 이름과 판.


async def test_구조_우선이_아닌_전략_이름은_설정_오류다() -> None:
    other = ChunkingConfig(strategy="semantic", max_tokens=100, overlap_tokens=0)

    with pytest.raises(ConfigurationError, match="구조 우선 전략이 아닌 이름이다: semantic"):
        await StructureFirstChunker().chunk(blocks_of(("p", "본문")), other, CharMeter())


def test_전략_이름으로_구현을_고르고_모르는_이름은_설정_오류다() -> None:
    assert isinstance(chunker_for("structure_first"), StructureFirstChunker)
    with pytest.raises(ConfigurationError, match="모르는 청킹 전략이다: semantic"):
        chunker_for("semantic")


def test_청킹이_아는_전략_이름은_색인_판_요소_계산도_안다() -> None:
    for strategy in STRATEGIES:
        compute_index_elements(
            "BAAI/bge-m3",
            1024,
            ChunkingConfig(strategy=strategy, max_tokens=512, overlap_tokens=64),
        )


async def test_구조_우선_전략_판_1의_표본은_고정된_조각을_낸다() -> None:
    # 이 표본이 달라지면 전략의 규칙이 바뀐 것이다. 규칙을 바꾸면 `STRUCTURE_FIRST_VERSION`을 올리고
    # 이 표본의 기대를 새 판 것으로 고친다(청킹 해시가 달라져 "재색인 필요"로 드러난다).
    assert STRUCTURE_FIRST_VERSION == "1"
    blocks = blocks_of(
        ("h1", "제3조 정의", 1),
        ("p", PARAGRAPH_OF_FOUR, 1),
        ("t", "머리\n가 | 1\n나 | 2", 2),
    )

    drafts = await chunk(blocks, 60, overlap=10)

    # 문단 39글자와 표 14글자를 이으면 절 경로 줄 6글자와 그 뒤 빈 줄 2글자, 두 블록 사이 빈 줄
    # 2글자를 더해 63이라 상한 60을 넘는다. 표는 둘째 조각으로 가고 첫째 조각의 끝 문장 하나가
    # 겹친다.
    assert [(draft.text, draft.token_count) for draft in drafts] == [
        (PARAGRAPH_OF_FOUR, 47),
        (f"{FOURTH}\n\n머리\n가 | 1\n나 | 2", 33),
    ]
