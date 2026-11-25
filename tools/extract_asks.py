"""세션 기록에서 선택 화면의 질문·선택지·답과 서브에이전트의 브리프·보고를 뽑는다.

`grilling`은 답을 일지·명세·ADR로 옮길 때 고른 선택지의 설명을 글자 그대로 옮기라고 한다. 그 글은
세션 기록(JSONL)에만 온전히 있어서, 설계 인터뷰 세션마다 스크래치패드에 스크립트를 새로 썼고 첫 판이
직접 친 답을 호출 전체의 답으로 붙여 틀린 적이 있다(대기열 `extract-asks-tool`). 컨텍스트가
압축된 뒤에도 기록은 압축 전의 줄을 그대로 갖고 있어, 압축으로 사라진 질문의 글과 서브에이전트의
브리프·보고를 되찾는 길도 같다(대기열 `review-report-journal-lag` 10회차).

두 가지를 낸다.
- `asks`: `AskUserQuestion` 호출을 질문 하나씩 낸다. 질문, 머리, 선택지마다 라벨·설명·미리보기, 답.
  답은 고른 라벨, 직접 친 원문, 거부, 오류, 결과 없음으로 가른다. 여러 개를 고르는 질문은 고른
  라벨들과 직접 친 글을 가른다. 답에 붙은 메모와 고른 미리보기도 낸다.
- `agents`: 서브에이전트(`Agent` 호출)마다 브리프(`prompt`)와 최종 보고를 낸다. 보고는 하네스가
  `queue-operation`으로 넣은 `<agent-message from="…">` 글에서 머리 문단과 두 칸 들여쓰기를 걷은
  원문이다. 같은 보고가 여러 줄에 되풀이돼도 한 번만 낸다(그래서 같은 에이전트가 같은 글로 두 번
  보고해도 한 번으로 센다).

읽는 줄(실제 기록 Claude Code 2.1.309에서 손으로 봤다, 근거는 티켓
`.scratch/harness/issues/session-asks-extractor.md`).
- 호출은 `type: assistant` 줄의 `tool_use`다. 같은 호출이 `api-request-blob` 줄과 `wireToolInputs`에
  되풀이되므로 `assistant` 줄만 읽고, 같은 호출 id는 첫 줄만 센다.
- 답은 `type: user` 줄의 `tool_result`와 같은 줄의 `toolUseResult`(`answers`: 질문 글 → 답,
  `annotations`: 질문 글 → `preview`·`notes`)다. 답은 질문 글로 짝지으므로 질문마다 따로 붙는다.
- 보고는 `queue-operation`의 `enqueue` 줄과 `attachment`의 `queued_command`에서 읽는다.
- 위 네 종류(`assistant`, `user`, `queue-operation`, `attachment`) 밖의 줄은 읽자마자 버려, 큰
  기록을 읽어도 필요한 줄만 메모리에 남는다. 파일은 UTF-8(BOM이 있어도 된다)로 읽는다.

못 보는 것. 아래 항목마다 `tests/tools/test_extract_asks.py`의 시험 하나가 그 입력을 고정한다.
- 결과에 `toolUseResult`의 `answers`가 없는 호출(옛 기록 모양)은 질문과 선택지만 내고, 답은 결과
  글을 그대로 붙여 "구조가 없다"고 적는다.
- 거부는 `toolUseResult`가 문자열 `User rejected tool use`일 때만 거부로 적는다. `is_error`이거나
  다른 문자열인 결과(입력 검증 오류, 훅이 막은 것)는 거부가 아니라 오류로 적고 결과 글을 붙인다.
  훅이 막은 호출의 결과 모양은 이 저장소의 기록에서 본 적이 없다.
- 여러 개를 고르는 질문에서 직접 친 글이 고른 라벨보다 앞에 오면 답 전체를 직접 친 글로 낸다.
  답 글에 라벨의 경계가 없어서다. 반대로 아무것도 고르지 않고 `라벨, 글`로 시작하는 글을 쳐도 그
  라벨을 고른 것으로 읽는다.
- 답을 질문 글로 짝지으므로 한 호출 안에 같은 질문 글이 둘이면 둘이 같은 답을 받는다.
- 결과에 `agentId`가 없는 서브에이전트 호출은 동기로 돈 것으로 어림하고, 브리프만 내며 보고는 도구
  결과에 있다고 적는다. 동기 결과가 `agentId`도 함께 가지면 보고를 찾지 못했다고 적는다. 어느 쪽도
  본 적이 없다. 이 저장소의 기록에서 센 결과는 메인 폴더 80건과 워크트리 폴더까지 합친 472건이
  모두 `async_launched`였다(리뷰어가 스크래치 스크립트로 센 값이고 커밋한 프로브가 아니다).
- 서브에이전트가 자기 일을 적은 기록 파일(`subagents/`)은 열지 않는다(인자로 준 파일 하나만 읽는다).
  `SendMessage`로 보낸 이어받기 글도 읽지 않고, 돌아온 보고만 에이전트 id로 묶는다. 이름(`name`)을
  붙여 띄운 에이전트는 보고가 그 이름으로 돌아오므로 이름으로도 묶고, 같은 이름을 두 번 쓰면 보고는
  나중에 띄운 쪽에 붙는다.
- 보고 글 하나에 `<agent-message>`가 둘 들어 있으면 첫 보고에 둘째 메시지 전체가 든다.
- UTF-8로 읽지 못하는 바이트(세션이 아직 쓰는 중이라 한글 중간에서 잘린 마지막 줄)는 대체 글자로
  바꿔 읽는다. 그 줄이 JSON으로 읽히지 않으면 읽지 못한 줄로 세고 앞의 줄은 그대로 읽는다.
- 한 `user` 줄에 `tool_result`가 둘 이상이면 그 줄의 `toolUseResult`가 어느 결과의 것인지 알 수 없어
  쓰지 않는다. 질문은 구조 없는 결과로, 에이전트는 id 없이 낸다.
- 기록의 글에 짝 없는 서로게이트 문자(`\ud800` 같은 것)가 있으면 `\ud800` 꼴로 바꿔 낸다. 글자
  그대로 내지 못하는 그 글자만 그렇다.
- 터미널 제어 문자(ESC 등)는 걸러 내지 않고 그대로 낸다. 모델 세션이 파이프로 읽는 쓰임이 주라서다.
- 여러 줄 글은 줄마다 네 칸 들여 써서 낸다. 일지에 옮길 때는 그 들여쓰기를 걷고 옮긴다. 한 줄로 찍는
  칸(머리, 라벨, 에이전트 설명, 이름, id, 시각)의 줄바꿈은 `\n` 두 글자로 바꿔 구조를 흉내 내지
  못하게 한다.

쓰임: `uv run python tools/extract_asks.py asks <세션 기록.jsonl> [--only N]`,
`uv run python tools/extract_asks.py agents <세션 기록.jsonl> [--only N]`. 기록은
`~/.claude/projects/<프로젝트 폴더>/<세션 ID>.jsonl`이고, 워크트리 세션은 폴더 이름에
`--claude-worktrees-<이름>`이 붙는다. `--only N`은 N번째 호출(`asks`)이나 N번째 에이전트(`agents`)만
낸다. 종료 0은 냈다, 1은 낼 것이 없다(호출이 없거나 번호가 범위 밖), 2는 인자가 틀렸거나 파일을
읽지 못했다. 읽지 못한 줄은 세어 출력 끝(종료 1이면 오류 글 끝)에 적는다.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type Record = dict[str, Json]
type Numbered = Sequence[tuple[int, Record]]
type Status = Literal["answered", "rejected", "error", "no_result", "unstructured"]

ASK_TOOL = "AskUserQuestion"
REJECTED = "User rejected tool use"
AGENT_TOOLS = frozenset({"Agent", "Task"})
INDENT = "    "
HANDBACK = re.compile(
    r'\A<agent-message from="([^"]+)">\n(.*?)(?:\n</agent-message>)?\s*\Z', re.DOTALL
)
REPORT_MARKER = "The report follows:\n"
KEPT_TYPES = frozenset({"assistant", "user", "queue-operation", "attachment"})


@dataclass
class Option:
    label: str
    description: str
    preview: str | None


@dataclass
class Question:
    text: str
    header: str
    multi: bool
    options: list[Option]


@dataclass
class Answer:
    """`picked`는 고른 라벨, `typed`는 선택지에 없는 직접 친 글이다."""

    picked: list[str]
    typed: str | None


@dataclass
class AskCall:
    """`status`는 answered, rejected, no_result, unstructured 중 하나다.

    `answers`, `notes`, `previews`는 `questions`와 같은 차례다.
    """

    number: int
    line: int
    timestamp: str | None
    tool_id: str
    questions: list[Question]
    status: Status = "no_result"
    answers: list[Answer | None] = field(default_factory=list[Answer | None])
    notes: list[str | None] = field(default_factory=list[str | None])
    previews: list[str | None] = field(default_factory=list[str | None])
    raw_result: str = ""


@dataclass
class AgentRun:
    agent_id: str | None
    description: str | None
    brief: str | None
    line: int | None
    timestamp: str | None
    name: str | None = None
    reports: list[str] = field(default_factory=list[str])


def _obj(value: Json | None) -> Record | None:
    return value if isinstance(value, dict) else None


def _items(value: Json | None) -> list[Json]:
    return value if isinstance(value, list) else []


def _str(value: Json | None) -> str | None:
    return value if isinstance(value, str) else None


def _parts(record: Record) -> list[Record]:
    """`message.content`의 블록들. 글자 하나짜리 content면 빈 목록이다."""
    message = _obj(record.get("message"))
    content = message.get("content") if message is not None else None
    return [part for item in _items(content) if (part := _obj(item)) is not None]


def indent_block(text: str, prefix: str = INDENT) -> str:
    """줄마다 prefix를 붙인다. 빈 줄은 그대로 둔다."""
    return "\n".join(prefix + line if line else line for line in text.split("\n"))


def one_line(text: str) -> str:
    """한 줄로 찍는 칸의 줄바꿈을 `\\n` 두 글자로 바꿔, 칸 안의 글이 출력 구조를 흉내 내지 못하게
    한다."""
    return text.replace("\r", "\\r").replace("\n", "\\n")


def read_records(path: Path) -> tuple[list[tuple[int, Record]], int]:
    """(줄 번호, 줄)과 읽지 못한 줄 수. 줄 번호는 1부터다. `KEPT_TYPES` 밖의 줄은 버린다.
    `type`이 리스트나 객체인 줄은 집합 조회가 `TypeError`를 내므로 읽지 못한 줄로 센다."""
    records: list[tuple[int, Record]] = []
    broken = 0
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                parsed: Json = json.loads(raw)
            except ValueError:
                broken += 1
                continue
            if not isinstance(parsed, dict):
                broken += 1
            elif isinstance(parsed.get("type"), (list, dict)):
                broken += 1
            elif parsed.get("type") in KEPT_TYPES:
                records.append((number, parsed))
    return records, broken


def _questions(source: Record | None) -> list[Question]:
    questions: list[Question] = []
    for item in _items(source.get("questions") if source is not None else None):
        raw = _obj(item)
        if raw is None:
            continue
        options: list[Option] = []
        for entry in _items(raw.get("options")):
            option = _obj(entry)
            if option is None:
                continue
            options.append(
                Option(
                    label=_str(option.get("label")) or "",
                    description=_str(option.get("description")) or "",
                    preview=_str(option.get("preview")),
                )
            )
        questions.append(
            Question(
                text=_str(raw.get("question")) or "",
                header=_str(raw.get("header")) or "",
                multi=raw.get("multiSelect") is True,
                options=options,
            )
        )
    return questions


def _peel(text: str, labels: list[str]) -> tuple[list[str], str]:
    """앞에서부터 라벨을 벗기고(라벨 사이는 `, `) 남은 글을 준다. 긴 라벨이 먼저다."""
    ordered = sorted((label for label in labels if label), key=len, reverse=True)
    picked: list[str] = []
    rest = text
    while rest:
        for label in ordered:
            if rest == label:
                picked.append(label)
                rest = ""
                break
            if rest.startswith(label + ", "):
                picked.append(label)
                rest = rest[len(label) + 2 :]
                break
        else:
            break
    return picked, rest


def split_answer(raw: Json, question: Question) -> Answer:
    """답 하나를 고른 라벨과 직접 친 글로 가른다."""
    labels = [option.label for option in question.options]
    if isinstance(raw, list):
        strings = [
            item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in raw
        ]
        picked = [item for item in strings if item in labels]
        typed = ", ".join(item for item in strings if item not in labels)
        return Answer(picked, typed or None)
    text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    if question.multi:
        picked, rest = _peel(text, labels)
        return Answer(picked, rest or None)
    if text in labels:
        return Answer([text], None)
    return Answer([], text or None)


def _result_text(part: Record) -> str:
    content = part.get("content")
    if isinstance(content, str):
        return content
    texts = [
        text for item in _items(content) if (obj := _obj(item)) and (text := _str(obj.get("text")))
    ]
    return "\n".join(texts)


def _line_result(record: Record) -> Json | None:
    """줄의 `toolUseResult`. `tool_result`가 둘 이상이면 어느 결과의 것인지 알 수 없어
    `None`이다."""
    results = [part for part in _parts(record) if part.get("type") == "tool_result"]
    return record.get("toolUseResult") if len(results) == 1 else None


def _with_result(call: AskCall, record: Record, part: Record) -> AskCall:
    """결과 줄을 읽어 상태와 답을 채운 새 호출을 준다."""
    outcome = _line_result(record)
    detail = _obj(outcome)
    answers = _obj(detail.get("answers")) if detail is not None else None
    if answers is not None and detail is not None:
        questions = call.questions or _questions(detail)
        annotations = _obj(detail.get("annotations")) or {}
        raws = [answers.get(question.text) for question in questions]
        marks = [_obj(annotations.get(question.text)) or {} for question in questions]
        return replace(
            call,
            status="answered",
            questions=questions,
            answers=[
                split_answer(raw, question) if raw is not None else None
                for raw, question in zip(raws, questions, strict=True)
            ],
            notes=[_str(mark.get("notes")) for mark in marks],
            previews=[_str(mark.get("preview")) for mark in marks],
        )
    if outcome == REJECTED:
        return replace(call, status="rejected")
    if part.get("is_error") is True or isinstance(outcome, str):
        text = _result_text(part) or (outcome if isinstance(outcome, str) else "")
        return replace(call, status="error", raw_result=text)
    return replace(call, status="unstructured", raw_result=_result_text(part))


def collect_asks(records: Numbered) -> list[AskCall]:
    calls: list[AskCall] = []
    by_id: dict[str, AskCall] = {}
    for line, record in records:
        kind = record.get("type")
        if kind == "assistant":
            for part in _parts(record):
                tool_id = _str(part.get("id"))
                if part.get("type") != "tool_use" or part.get("name") != ASK_TOOL:
                    continue
                if tool_id is None or tool_id in by_id:
                    continue
                questions = _questions(_obj(part.get("input")))
                call = AskCall(
                    number=len(calls) + 1,
                    line=line,
                    timestamp=_str(record.get("timestamp")),
                    tool_id=tool_id,
                    questions=questions,
                    answers=[None] * len(questions),
                    notes=[None] * len(questions),
                    previews=[None] * len(questions),
                )
                calls.append(call)
                by_id[tool_id] = call
        elif kind == "user":
            for part in _parts(record):
                if part.get("type") != "tool_result":
                    continue
                call = by_id.get(_str(part.get("tool_use_id")) or "")
                if call is not None and call.status == "no_result":
                    updated = _with_result(call, record, part)
                    calls[call.number - 1] = updated
                    by_id[call.tool_id] = updated
    return calls


def parse_handback(content: str) -> tuple[str, str] | None:
    """하네스가 넣은 서브에이전트 보고 글에서 (에이전트 id, 보고 원문)을 푼다."""
    match = HANDBACK.match(content)
    if match is None:
        return None
    inner = match.group(2)
    marker = inner.find(REPORT_MARKER)
    body = inner[marker + len(REPORT_MARKER) :] if marker >= 0 else inner
    return match.group(1), "\n".join(line.removeprefix("  ") for line in body.split("\n"))


def _handback_of(record: Record) -> tuple[str, str] | None:
    if record.get("type") == "queue-operation" and record.get("operation") == "enqueue":
        content = _str(record.get("content"))
        return parse_handback(content) if content is not None else None
    attachment = _obj(record.get("attachment"))
    if record.get("type") == "attachment" and attachment is not None:
        if attachment.get("type") == "queued_command":
            prompt = _str(attachment.get("prompt"))
            return parse_handback(prompt) if prompt is not None else None
    return None


def collect_agents(records: Numbered) -> list[AgentRun]:
    runs: list[AgentRun] = []
    by_tool: dict[str, AgentRun] = {}
    by_address: dict[str, AgentRun] = {}
    for line, record in records:
        for part in _parts(record) if record.get("type") in ("assistant", "user") else []:
            if record.get("type") == "assistant":
                tool_id = _str(part.get("id"))
                if part.get("type") != "tool_use" or part.get("name") not in AGENT_TOOLS:
                    continue
                if tool_id is None or tool_id in by_tool:
                    continue
                request = _obj(part.get("input")) or {}
                run = AgentRun(
                    agent_id=None,
                    description=_str(request.get("description")),
                    brief=_str(request.get("prompt")),
                    line=line,
                    timestamp=_str(record.get("timestamp")),
                    name=_str(request.get("name")),
                )
                runs.append(run)
                by_tool[tool_id] = run
                if run.name:
                    by_address[run.name] = run  # 이름을 붙여 띄우면 보고가 그 이름으로 돌아온다
            elif part.get("type") == "tool_result":
                run = by_tool.get(_str(part.get("tool_use_id")) or "")
                outcome = _obj(_line_result(record))
                agent_id = _str(outcome.get("agentId")) if outcome is not None else None
                if run is not None and run.agent_id is None and agent_id is not None:
                    run.agent_id = agent_id
                    by_address[agent_id] = run
        handback = _handback_of(record)
        if handback is None:
            continue
        agent_id, body = handback
        run = by_address.get(agent_id)
        if run is None:
            run = AgentRun(agent_id, None, None, None, None)
            runs.append(run)
            by_address[agent_id] = run
        if body not in run.reports:
            run.reports.append(body)
    return runs


def _block(label: str, text: str) -> str:
    """한 줄이면 `라벨: 글`, 여러 줄이면 라벨 줄 아래에 들여 쓴 글이다."""
    if "\n" not in text:
        return f"{label}: {text}"
    return f"{label}:\n{indent_block(text)}"


def _render_answer(call: AskCall, index: int) -> list[str]:
    if call.status == "rejected":
        return ["답: 거부됨 (사용자가 이 호출을 거부했다)"]
    if call.status == "error":
        return [_block("답: 호출이 오류로 끝났다", call.raw_result)]
    if call.status == "no_result":
        return ["답: 결과가 기록에 없다"]
    if call.status == "unstructured":
        return [_block("답: 결과 글만 있고 구조가 없다", call.raw_result)]
    answer = call.answers[index] if index < len(call.answers) else None
    if answer is None:
        return ["답: 이 질문의 답이 기록에 없다"]
    lines: list[str] = []
    lines.extend(_block("답: 고른 것", label) for label in answer.picked)
    if answer.typed is not None:
        lines.append(_block("답: 직접 입력", answer.typed))
    if not lines:
        lines.append("답: 빈 답")
    return lines


def _render_question(call: AskCall, index: int, total: int) -> str:
    question = call.questions[index]
    answer = call.answers[index] if index < len(call.answers) else None
    picked = answer.picked if answer is not None else []
    stamp = f" · {one_line(call.timestamp)}" if call.timestamp else ""
    out = [
        f"## 호출 {call.number}/{total} 질문 {index + 1}/{len(call.questions)}"
        f" · 줄 {call.line}{stamp}",
        f"머리: {one_line(question.header)}",
        _block("질문", question.text),
        "선택지:",
    ]
    for number, option in enumerate(question.options, start=1):
        mark = " ← 고른 것" if option.label in picked else ""
        out.append(f" {number}. {one_line(option.label)}{mark}")
        out.append(indent_block(_block("설명", option.description)))
        if option.preview is not None:
            out.append(indent_block(_block("미리보기", option.preview)))
    out.extend(_render_answer(call, index))
    note = call.notes[index] if index < len(call.notes) else None
    preview = call.previews[index] if index < len(call.previews) else None
    if note is not None:
        out.append(_block("메모", note))
    if preview is not None:
        out.append(_block("고른 미리보기", preview))
    return "\n".join(out)


def render_asks(calls: list[AskCall], only: int | None) -> str:
    blocks: list[str] = []
    for call in calls:
        if only is not None and call.number != only:
            continue
        if not call.questions:
            blocks.append(f"## 호출 {call.number}/{len(calls)} · 줄 {call.line}\n(질문이 없다)")
        blocks.extend(_render_question(call, i, len(calls)) for i in range(len(call.questions)))
    return "\n\n".join(blocks)


def render_agents(runs: list[AgentRun], only: int | None) -> str:
    blocks: list[str] = []
    for number, run in enumerate(runs, start=1):
        if only is not None and number != only:
            continue
        title = one_line(run.description or "(설명이 기록에 없다)")
        where = f" · 줄 {run.line}" if run.line is not None else ""
        agent = (
            one_line(run.agent_id)
            if run.agent_id
            else "(에이전트 id가 기록에 없다. 동기로 돈 호출이면 보고는 도구 결과에 있다)"
        )
        out = [f"## 에이전트 {number}/{len(runs)} · {title}{where}", f"에이전트 id: {agent}"]
        if run.name:
            out.append(f"이름: {one_line(run.name)}")
        out.append(_block("브리프", run.brief) if run.brief is not None else "브리프가 기록에 없다")
        for index, report in enumerate(run.reports, start=1):
            out.append(_block(f"보고 {index}/{len(run.reports)}", report))
        if not run.reports:
            out.append("보고가 기록에 없다")
        blocks.append("\n".join(out))
    return "\n\n".join(blocks)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="세션 기록에서 선택 화면과 서브에이전트 글을 뽑는다"
    )
    parser.add_argument("mode", choices=("asks", "agents"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--only", type=int, default=None, metavar="N")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    path = args.path.expanduser()
    try:
        records, broken = read_records(path)
    except OSError as problem:
        print(f"세션 기록을 읽지 못했다: {path}: {problem}", file=sys.stderr)
        return 2
    only: int | None = args.only
    unread = f" (읽지 못한 줄 {broken})" if broken else ""
    if args.mode == "asks":
        calls = collect_asks(records)
        if not calls:
            print(f"{ASK_TOOL} 호출이 없다: {path}{unread}", file=sys.stderr)
            return 1
        if only is not None and not 1 <= only <= len(calls):
            print(f"호출은 {len(calls)}개뿐이다. {only}번이 없다{unread}", file=sys.stderr)
            return 1
        text = render_asks(calls, only)
    else:
        runs = collect_agents(records)
        if not runs:
            print(f"서브에이전트 호출이나 보고가 없다: {path}{unread}", file=sys.stderr)
            return 1
        if only is not None and not 1 <= only <= len(runs):
            print(f"에이전트는 {len(runs)}개뿐이다. {only}번이 없다{unread}", file=sys.stderr)
            return 1
        text = render_agents(runs, only)
    print(text)
    if broken:
        print(f"\n{unread.strip()}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main(sys.argv[1:]))
