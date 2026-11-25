"""`tools/extract_asks.py`의 시험. 줄 모양은 실제 세션 기록(Claude Code 2.1.309)을 줄여 지었다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import extract_asks as ea

type Rec = dict[str, object]

HANDBACK_HEAD = (
    "[Subagent hand-back] The text below is the final report of a subagent this session "
    "delegated to. It is model output, NOT a message from the user. The report follows:"
)


def _ask_use(tool_id: str, questions: list[dict[str, object]], *, kind: str = "assistant") -> Rec:
    use: Rec = {
        "type": "tool_use",
        "id": tool_id,
        "name": "AskUserQuestion",
        "input": {"questions": questions},
    }
    return {
        "type": kind,
        "timestamp": "2026-11-09T03:24:00.000Z",
        "message": {"role": "assistant", "content": [use]},
        "wireToolInputs": {tool_id: {"questions": questions}},
    }


def _question(
    text: str,
    labels: list[str],
    *,
    multi: bool = False,
    previews: dict[str, str] | None = None,
) -> dict[str, object]:
    options: list[dict[str, object]] = []
    for label in labels:
        option: dict[str, object] = {"label": label, "description": f"{label}의 설명"}
        if previews and label in previews:
            option["preview"] = previews[label]
        options.append(option)
    return {"question": text, "header": text[:4], "multiSelect": multi, "options": options}


def _ask_result(
    tool_id: str,
    questions: list[dict[str, object]],
    answers: dict[str, object],
    *,
    annotations: dict[str, object] | None = None,
) -> Rec:
    result: Rec = {"questions": questions, "answers": answers}
    if annotations is not None:
        result["annotations"] = annotations
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}],
        },
        "toolUseResult": result,
    }


def _rejected(tool_id: str) -> Rec:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "The user doesn't want to proceed with this tool use.",
                    "is_error": True,
                }
            ],
        },
        "toolUseResult": "User rejected tool use",
    }


def _agent_use(tool_id: str, description: str, prompt: str, name: str | None = None) -> Rec:
    request: Rec = {"description": description, "prompt": prompt, "subagent_type": "Explore"}
    if name is not None:
        request["name"] = name
    use: Rec = {"type": "tool_use", "id": tool_id, "name": "Agent", "input": request}
    return {
        "type": "assistant",
        "timestamp": "2026-11-20T10:01:00.000Z",
        "message": {"role": "assistant", "content": [use]},
    }


def _agent_launched(tool_id: str, agent_id: str) -> Rec:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": [{"type": "text", "text": "Async agent launched successfully."}],
                }
            ],
        },
        "toolUseResult": {"isAsync": True, "status": "async_launched", "agentId": agent_id},
    }


def _handback_content(agent_id: str, report: str) -> str:
    indented = "\n".join(f"  {line}".rstrip() if line else "  " for line in report.split("\n"))
    return f'<agent-message from="{agent_id}">\n{HANDBACK_HEAD}\n{indented}\n</agent-message>'


def _enqueue(agent_id: str, report: str, operation: str = "enqueue") -> Rec:
    return {
        "type": "queue-operation",
        "operation": operation,
        "timestamp": "2026-11-20T10:06:07.768Z",
        "content": _handback_content(agent_id, report),
    }


def _queued_attachment(agent_id: str, report: str) -> Rec:
    return {
        "type": "attachment",
        "attachment": {
            "type": "queued_command",
            "prompt": _handback_content(agent_id, report),
        },
    }


def _write(path: Path, records: list[Rec], *, extra_lines: tuple[str, ...] = ()) -> Path:
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join([*lines, *extra_lines]) + "\n", encoding="utf-8")
    return path


def _numbered(records: list[Rec]) -> list[tuple[int, ea.Record]]:
    """파일에서 읽은 것과 같은 모양(줄 번호는 1부터)으로 되돌린다."""
    numbered: list[tuple[int, ea.Record]] = []
    for number, record in enumerate(records, start=1):
        parsed: ea.Record = json.loads(json.dumps(record, ensure_ascii=False))
        numbered.append((number, parsed))
    return numbered


def _answer_of(calls: list[ea.AskCall], call: int, question: int) -> ea.Answer:
    answer = calls[call].answers[question]
    assert answer is not None
    return answer


def test_호출_하나의_질문_둘을_질문_단위로_낸다() -> None:
    qs = [
        _question("저장소는 어디에 둘까요?", ["디스크", "객체 저장소"]),
        _question("큐는요?", ["PG", "MQ"]),
    ]
    records = [
        _ask_use("t1", qs),
        _ask_result("t1", qs, {"저장소는 어디에 둘까요?": "객체 저장소", "큐는요?": "PG"}),
    ]
    calls = ea.collect_asks(_numbered(records))
    assert len(calls) == 1
    assert [q.text for q in calls[0].questions] == ["저장소는 어디에 둘까요?", "큐는요?"]
    assert [o.label for o in calls[0].questions[0].options] == ["디스크", "객체 저장소"]
    assert calls[0].questions[0].options[0].description == "디스크의 설명"
    assert _answer_of(calls, 0, 0).picked == ["객체 저장소"]
    assert _answer_of(calls, 0, 1).picked == ["PG"]


def test_직접_친_답은_선택지에_없는_원문으로_가른다() -> None:
    qs = [_question("묶음 단위는?", ["하나", "여럿"])]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음 단위는?": "보통은 어떻게 해?"})]
    calls = ea.collect_asks(_numbered(records))
    answer = _answer_of(calls, 0, 0)
    assert answer.picked == []
    assert answer.typed == "보통은 어떻게 해?", f"직접 친 글이 {answer.typed!r}로 읽힌다"


def test_직접_친_답이_같은_호출의_다른_질문_답으로_붙지_않는다() -> None:
    # 스크래치 스크립트의 첫 판은 직접 친 답을 호출 전체의 답으로 붙였다(대기열 extract-asks-tool)
    qs = [_question("가", ["x", "y"]), _question("나", ["p", "q"]), _question("다", ["m", "n"])]
    records = [
        _ask_use("t1", qs),
        _ask_result("t1", qs, {"가": "x", "나": "RabbitMQ는 어때?", "다": "n"}),
    ]
    calls = ea.collect_asks(_numbered(records))
    assert (_answer_of(calls, 0, 0).picked, _answer_of(calls, 0, 0).typed) == (["x"], None)
    assert (_answer_of(calls, 0, 1).picked, _answer_of(calls, 0, 1).typed) == (
        [],
        "RabbitMQ는 어때?",
    )
    assert (_answer_of(calls, 0, 2).picked, _answer_of(calls, 0, 2).typed) == (["n"], None)


def test_거부한_호출은_거부됨으로_적는다() -> None:
    qs = [_question("가", ["x", "y"])]
    records = [_ask_use("t1", qs), _rejected("t1")]
    calls = ea.collect_asks(_numbered(records))
    assert calls[0].status == "rejected"
    assert calls[0].answers == [None]
    assert "답: 거부됨" in ea.render_asks(calls, None)


def test_거부가_아닌_오류_결과는_오류로_적고_결과_글을_붙인다() -> None:
    qs = [_question("가", ["x", "y"])]
    blocked: Rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": "PreToolUse hook blocked this call: 처음 보는 화면이라 막았다",
                    "is_error": True,
                }
            ],
        },
        "toolUseResult": "PreToolUse hook blocked this call",
    }
    calls = ea.collect_asks(_numbered([_ask_use("t1", qs), blocked]))
    assert calls[0].status == "error"
    text = ea.render_asks(calls, None)
    assert "답: 호출이 오류로 끝났다: PreToolUse hook blocked this call: 처음 보는 화면이라" in text
    assert "거부됨" not in text


def test_결과가_없는_호출은_결과_없음으로_적는다() -> None:
    qs = [_question("가", ["x", "y"])]
    calls = ea.collect_asks(_numbered([_ask_use("t1", qs)]))
    assert calls[0].status == "no_result"
    assert "결과가 기록에 없다" in ea.render_asks(calls, None)


def test_assistant가_아닌_줄의_호출은_id가_달라도_세지_않는다() -> None:
    qs = [_question("가", ["x", "y"])]
    records = [
        _ask_use("t1", qs),
        _ask_use("t1", qs, kind="api-request-blob"),
        _ask_use("t2", qs, kind="api-request-blob"),
        _ask_result("t1", qs, {"가": "x"}),
    ]
    calls = ea.collect_asks(_numbered(records))
    ids = [call.tool_id for call in calls]
    assert ids == ["t1"], f"센 호출 id가 {ids}이다"


def test_같은_호출_id가_assistant_줄에_두_번_나와도_한_번만_센다() -> None:
    qs = [_question("가", ["x", "y"])]
    records = [_ask_use("t1", qs), _ask_use("t1", qs), _ask_result("t1", qs, {"가": "y"})]
    calls = ea.collect_asks(_numbered(records))
    assert len(calls) == 1, f"호출을 {len(calls)}개로 센다"
    assert calls[0].line == 1


def test_호출_번호는_나온_차례이고_압축_경계_앞뒤를_모두_센다() -> None:
    q1 = [_question("첫째", ["a", "b"])]
    q2 = [_question("둘째", ["c", "d"])]
    records: list[Rec] = [
        _ask_use("t1", q1),
        _ask_result("t1", q1, {"첫째": "a"}),
        {"type": "system", "subtype": "compact_boundary"},
        _ask_use("t2", q2),
        _ask_result("t2", q2, {"둘째": "d"}),
    ]
    calls = ea.collect_asks(_numbered(records))
    assert [(c.number, c.questions[0].text) for c in calls] == [(1, "첫째"), (2, "둘째")]


def test_여러_개_고르기는_목록_모양과_문자열_모양을_모두_읽는다() -> None:
    labels = ["코드 구조 넷", "린터 짝, 둘", "테스트 둘"]
    qs = [_question("묶음?", labels, multi=True)]
    as_list = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음?": ["코드 구조 넷", "테스트 둘"]})]
    as_text = [
        _ask_use("t1", qs),
        _ask_result("t1", qs, {"묶음?": "코드 구조 넷, 린터 짝, 둘, 테스트 둘"}),
    ]
    from_list = ea.collect_asks(_numbered(as_list))
    from_text = ea.collect_asks(_numbered(as_text))
    assert _answer_of(from_list, 0, 0).picked == ["코드 구조 넷", "테스트 둘"]
    # 라벨 안의 쉼표가 라벨을 둘로 쪼개지 않는다
    assert _answer_of(from_text, 0, 0).picked == ["코드 구조 넷", "린터 짝, 둘", "테스트 둘"]


def test_여러_개_고르기에서_고른_라벨_뒤에_직접_친_글을_가른다() -> None:
    qs = [_question("묶음?", ["하나", "둘"], multi=True)]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음?": "하나, 셋도 넣어 줘"})]
    answer = _answer_of(ea.collect_asks(_numbered(records)), 0, 0)
    assert answer.picked == ["하나"]
    assert answer.typed == "셋도 넣어 줘"


def test_메모와_고른_미리보기를_질문에_붙인다() -> None:
    qs = [_question("요약대로?", ["그대로", "고친다"], previews={"그대로": "1. 첫째\n2. 둘째"})]
    ann: dict[str, object] = {"요약대로?": {"preview": "1. 첫째\n2. 둘째", "notes": "둘째는 빼 줘"}}
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"요약대로?": "그대로"}, annotations=ann)]
    calls = ea.collect_asks(_numbered(records))
    assert calls[0].questions[0].options[0].preview == "1. 첫째\n2. 둘째"
    assert calls[0].notes == ["둘째는 빼 줘"]
    assert calls[0].previews == ["1. 첫째\n2. 둘째"]


def test_선택지_설명과_질문_글을_글자_그대로_낸다() -> None:
    long_description = "첫 줄입니다.\n  둘째 줄은 들여 썼다.\n\n넷째 줄."
    qs: list[dict[str, object]] = [
        {
            "question": "되묻기?",
            "header": "머리",
            "multiSelect": False,
            "options": [
                {"label": "가", "description": long_description},
                {"label": "나", "description": "짧다"},
            ],
        }
    ]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"되묻기?": "가"})]
    calls = ea.collect_asks(_numbered(records))
    text = ea.render_asks(calls, None)
    assert "질문: 되묻기?" in text
    # 설명은 글자 그대로 나오고, 줄마다 네 칸씩 두 번 들여 쓴 것이 더해질 뿐이다
    assert "설명:\n" + ea.indent_block(ea.indent_block(long_description)) in text
    assert " 1. 가 ← 고른 것" in text
    assert " 2. 나\n" in text


def test_같은_질문_글이_한_호출에_둘이면_둘이_같은_답을_받는다() -> None:
    qs = [_question("같은 글?", ["x", "y"]), _question("같은 글?", ["x", "y"])]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"같은 글?": "y"})]
    calls = ea.collect_asks(_numbered(records))
    assert [answer.picked if answer else None for answer in calls[0].answers] == [["y"], ["y"]]


def test_호출_번호를_주면_그_호출만_낸다() -> None:
    q1 = [_question("첫째 질문", ["a", "b"])]
    q2 = [_question("둘째 질문", ["c", "d"])]
    records = [
        _ask_use("t1", q1),
        _ask_result("t1", q1, {"첫째 질문": "a"}),
        _ask_use("t2", q2),
        _ask_result("t2", q2, {"둘째 질문": "c"}),
    ]
    calls = ea.collect_asks(_numbered(records))
    only_second = ea.render_asks(calls, 2)
    assert "둘째 질문" in only_second
    assert "첫째 질문" not in only_second


def test_에이전트의_브리프와_보고를_짝짓는다() -> None:
    records: list[Rec] = [
        _agent_use("tu1", "코드 사실 조사", "코드만 읽고 보고해 주세요."),
        _agent_launched("tu1", "agent-a"),
        _enqueue("agent-a", "보고입니다.\n\n## 1. 표\n- 칸이 셋"),
    ]
    runs = ea.collect_agents(_numbered(records))
    assert len(runs) == 1
    assert runs[0].agent_id == "agent-a"
    assert runs[0].description == "코드 사실 조사"
    assert runs[0].brief == "코드만 읽고 보고해 주세요."
    assert runs[0].reports == ["보고입니다.\n\n## 1. 표\n- 칸이 셋"]


def test_같은_보고가_여러_줄에_되풀이돼도_한_번만_낸다() -> None:
    report = "보고 본문입니다."
    records: list[Rec] = [
        _agent_use("tu1", "조사", "브리프"),
        _agent_launched("tu1", "agent-a"),
        _enqueue("agent-a", report, "enqueue"),
        _queued_attachment("agent-a", report),
        _enqueue("agent-a", report, "remove"),
    ]
    runs = ea.collect_agents(_numbered(records))
    assert runs[0].reports == [report]


def test_보고의_머리_문단과_두_칸_들여쓰기를_걷는다() -> None:
    report = "첫 줄\n    - 들여 쓴 항목\n\n끝 줄"
    content = _handback_content("agent-a", report)
    assert ea.parse_handback(content) == ("agent-a", report)


def test_보고가_아직_없는_에이전트는_없다고_적는다() -> None:
    records: list[Rec] = [_agent_use("tu1", "조사", "브리프"), _agent_launched("tu1", "agent-a")]
    runs = ea.collect_agents(_numbered(records))
    assert runs[0].reports == []
    assert "보고가 기록에 없다" in ea.render_agents(runs, None)


def test_같은_에이전트의_보고_둘은_각각_낸다() -> None:
    records: list[Rec] = [
        _agent_use("tu1", "조사", "브리프"),
        _agent_launched("tu1", "agent-a"),
        _enqueue("agent-a", "첫 보고"),
        _enqueue("agent-a", "다시 일한 뒤의 보고"),
    ]
    runs = ea.collect_agents(_numbered(records))
    assert runs[0].reports == ["첫 보고", "다시 일한 뒤의 보고"]
    assert "보고 2/2" in ea.render_agents(runs, None)


def test_이름을_붙여_띄운_에이전트의_보고는_이름으로_브리프와_짝짓는다() -> None:
    # 실제 기록에서 `name: review-standards`로 띄운 에이전트의 보고가 그 이름으로 돌아왔다
    records: list[Rec] = [
        _agent_use("tu1", "표준 축 셀프 리뷰", "표준 축 브리프", name="review-standards"),
        _agent_launched("tu1", "agent-a"),
        _enqueue("review-standards", "표준 축 보고"),
    ]
    runs = ea.collect_agents(_numbered(records))
    assert len(runs) == 1, f"에이전트를 {len(runs)}개로 센다"
    assert (runs[0].agent_id, runs[0].name) == ("agent-a", "review-standards")
    assert runs[0].brief == "표준 축 브리프"
    assert runs[0].reports == ["표준 축 보고"]
    assert "이름: review-standards" in ea.render_agents(runs, None)


def test_같은_이름을_두_번_쓰면_보고는_나중에_띄운_에이전트에_붙는다() -> None:
    records: list[Rec] = [
        _agent_use("tu1", "첫째", "첫 브리프", name="review"),
        _agent_launched("tu1", "agent-a"),
        _agent_use("tu2", "둘째", "둘째 브리프", name="review"),
        _agent_launched("tu2", "agent-b"),
        _enqueue("review", "보고"),
    ]
    runs = ea.collect_agents(_numbered(records))
    assert [run.reports for run in runs] == [[], ["보고"]]


def test_브리프를_모르는_에이전트의_보고도_잃지_않는다() -> None:
    records: list[Rec] = [_enqueue("agent-z", "혼자 온 보고")]
    runs = ea.collect_agents(_numbered(records))
    assert runs[0].agent_id == "agent-z"
    assert runs[0].brief is None
    assert runs[0].reports == ["혼자 온 보고"]
    assert "브리프가 기록에 없다" in ea.render_agents(runs, None)


def test_에이전트_호출이_아닌_이름과_하네스_글이_아닌_큐_줄은_보지_않는다() -> None:
    other_use: Rec = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tu9", "name": "Bash", "input": {"command": "ls"}}
            ],
        },
    }
    notification: Rec = {
        "type": "queue-operation",
        "operation": "enqueue",
        "content": "<task-notification>\n<task-id>agent-a</task-id>\n</task-notification>",
    }
    plain: Rec = {"type": "queue-operation", "operation": "enqueue", "content": "그냥 사용자 글"}
    # 이어받기 글(SendMessage)은 에이전트 호출로 세지 않는다
    follow_up: Rec = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu8",
                    "name": "SendMessage",
                    "input": {"to": "agent-a", "message": "이어서 해 주세요"},
                }
            ],
        },
    }
    runs = ea.collect_agents(_numbered([other_use, follow_up, notification, plain]))
    assert runs == []


def test_보고_글_하나에_메시지가_둘이면_첫_보고에_둘째_메시지_전체가_든다() -> None:
    first = _handback_content("agent-a", "첫 보고")
    second = _handback_content("agent-b", "둘째 보고")
    parsed = ea.parse_handback(first + "\n" + second)
    assert parsed is not None
    assert parsed[0] == "agent-a"
    assert '<agent-message from="agent-b">' in parsed[1]
    assert "둘째 보고" in parsed[1]


def test_main은_질문을_글로_내고_종료_0이다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qs = [_question("저장소는?", ["디스크", "객체"])]
    path = _write(
        tmp_path / "s.jsonl", [_ask_use("t1", qs), _ask_result("t1", qs, {"저장소는?": "디스크"})]
    )
    assert ea.main(["asks", str(path)]) == 0
    out = capsys.readouterr().out
    assert "저장소는?" in out
    assert "디스크" in out


def test_main은_호출이_없으면_이유를_적고_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path / "s.jsonl", [{"type": "system", "subtype": "compact_boundary"}])
    assert ea.main(["asks", str(path)]) == 1
    assert "AskUserQuestion 호출이 없다" in capsys.readouterr().err


def test_main은_범위_밖_번호면_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qs = [_question("가", ["x", "y"])]
    path = _write(tmp_path / "s.jsonl", [_ask_use("t1", qs), _ask_result("t1", qs, {"가": "x"})])
    code = ea.main(["asks", str(path), "--only", "5"])
    assert code == 1, f"종료 코드가 {code}이다"
    assert "1개" in capsys.readouterr().err


def test_main은_파일이_없으면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ea.main(["asks", str(tmp_path / "없다.jsonl")]) == 2
    assert "읽지 못했다" in capsys.readouterr().err


def test_쓰는_중이라_한글_중간에서_잘린_마지막_줄은_읽지_못한_줄로_세고_앞의_줄은_읽는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qs = [_question("저장소는?", ["디스크", "객체 저장소"])]
    path = _write(
        tmp_path / "s.jsonl", [_ask_use("t1", qs), _ask_result("t1", qs, {"저장소는?": "디스크"})]
    )
    with path.open("ab") as handle:
        handle.write(b'{"type":"assistant","k":"\xed\x95')  # 한글 3바이트 가운데 2바이트에서 잘렸다
    assert ea.main(["asks", str(path)]) == 0
    out = capsys.readouterr().out
    assert "저장소는?" in out
    assert "읽지 못한 줄 1" in out


def test_UTF8_BOM으로_시작하는_파일의_첫_줄도_읽는다(tmp_path: Path) -> None:
    qs = [_question("가", ["x", "y"])]
    path = tmp_path / "s.jsonl"
    lines = [json.dumps(r, ensure_ascii=False) for r in (_ask_use("t1", qs),)]
    path.write_bytes(b"\xef\xbb\xbf" + "\n".join(lines).encode("utf-8") + b"\n")
    records, broken = ea.read_records(path)
    numbers = [number for number, _ in records]
    assert numbers == [1], f"읽은 줄 번호가 {numbers}이다"
    assert broken == 0


def test_필요한_네_종류_밖의_줄은_읽자마자_버리고_줄_번호는_그대로_둔다(tmp_path: Path) -> None:
    qs = [_question("가", ["x", "y"])]
    path = _write(
        tmp_path / "s.jsonl",
        [
            {"type": "system", "subtype": "compact_boundary"},
            _ask_use("t1", qs, kind="api-request-blob"),
            _ask_use("t2", qs),
        ],
    )
    records, broken = ea.read_records(path)
    numbers = [number for number, _ in records]
    assert numbers == [3], f"남긴 줄 번호가 {numbers}이다"
    assert broken == 0


def test_type이_리스트나_객체인_줄은_터지지_않고_읽지_못한_줄로_센다(tmp_path: Path) -> None:
    qs = [_question("가", ["x", "y"])]
    path = _write(
        tmp_path / "s.jsonl",
        [_ask_use("t1", qs), {"type": []}, {"type": {}}, {"type": 3}, {"no": "type"}],
    )
    records, broken = ea.read_records(path)
    numbers = [number for number, _ in records]
    assert numbers == [1], f"남긴 줄 번호가 {numbers}이다"
    assert broken == 2, f"읽지 못한 줄을 {broken}개로 센다"


def test_main은_인자가_틀리면_까닭을_적고_2로_끝난다(capsys: pytest.CaptureFixture[str]) -> None:
    assert ea.main(["모르는명령", "x"]) == 2
    assert "invalid choice: '모르는명령'" in capsys.readouterr().err


def test_main은_호출이_없는_종료_1에도_읽지_못한_줄_수를_적는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path / "s.jsonl", [], extra_lines=("{깨진 줄", "또 깨진 줄", "[3]"))
    assert ea.main(["asks", str(path)]) == 1
    assert "읽지 못한 줄 3" in capsys.readouterr().err
    assert ea.main(["agents", str(path)]) == 1
    assert "읽지 못한 줄 3" in capsys.readouterr().err


def test_읽지_못한_줄은_세어_끝에_적고_나머지는_읽는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qs = [_question("가", ["x", "y"])]
    path = _write(
        tmp_path / "s.jsonl",
        [_ask_use("t1", qs), _ask_result("t1", qs, {"가": "x"})],
        extra_lines=("{닫히지 않은 줄", "[1, 2]"),
    )
    assert ea.main(["asks", str(path)]) == 0
    assert "읽지 못한 줄 2" in capsys.readouterr().out


def test_main의_agents는_브리프와_보고를_낸다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(
        tmp_path / "s.jsonl",
        [
            _agent_use("tu1", "코드 사실 조사", "코드만 읽어 주세요."),
            _agent_launched("tu1", "agent-a"),
            _enqueue("agent-a", "보고 본문"),
        ],
    )
    assert ea.main(["agents", str(path)]) == 0
    out = capsys.readouterr().out
    assert "코드 사실 조사" in out
    assert "코드만 읽어 주세요." in out
    assert "보고 본문" in out


def test_main의_agents는_에이전트가_없으면_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path / "s.jsonl", [{"type": "system", "subtype": "compact_boundary"}])
    assert ea.main(["agents", str(path)]) == 1
    assert "서브에이전트" in capsys.readouterr().err


def test_답_구조가_없는_옛_결과는_결과_글을_붙여_구조가_없다고_적는다() -> None:
    qs = [_question("가", ["x", "y"])]
    old_result: Rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "User has answered: x"}
            ],
        },
    }
    calls = ea.collect_asks(_numbered([_ask_use("t1", qs), old_result]))
    assert calls[0].status == "unstructured"
    text = ea.render_asks(calls, None)
    assert "구조가 없다" in text
    assert "User has answered: x" in text


def test_여러_개_고르기에서_직접_친_글이_라벨_앞에_오면_답_전체를_직접_친_글로_낸다() -> None:
    qs = [_question("묶음?", ["하나", "둘"], multi=True)]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음?": "셋도 넣어 줘, 하나"})]
    answer = _answer_of(ea.collect_asks(_numbered(records)), 0, 0)
    assert answer.picked == []
    assert answer.typed == "셋도 넣어 줘, 하나"


def test_동기로_돈_에이전트는_브리프만_내고_보고는_도구_결과에_있다고_적는다() -> None:
    sync_result: Rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "동기 보고"}],
        },
        "toolUseResult": {
            "status": "completed",
            "content": [{"type": "text", "text": "동기 보고"}],
        },
    }
    runs = ea.collect_agents(_numbered([_agent_use("tu1", "조사", "브리프"), sync_result]))
    assert runs[0].agent_id is None
    assert runs[0].brief == "브리프"
    assert "도구 결과에 있다" in ea.render_agents(runs, None)


def test_main을_스크립트로_실제로_불러_한글이_깨지지_않게_낸다(tmp_path: Path) -> None:
    qs = [_question("저장소는 어디에 둘까요?", ["디스크", "객체 저장소"])]
    path = _write(
        tmp_path / "s.jsonl",
        [_ask_use("t1", qs), _ask_result("t1", qs, {"저장소는 어디에 둘까요?": "객체 저장소"})],
    )
    script = Path(__file__).resolve().parents[2] / "tools" / "extract_asks.py"
    # 설정의 PYTHONUTF8이 없는 환경에서도 한글이 UTF-8로 나와야 한다. 윈도 파이프는 cp949라서
    # 그 조건을 리눅스에서도 같게 만들려고 표준출력 인코딩을 cp949로 강제한다
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    env["PYTHONIOENCODING"] = "cp949"
    done = subprocess.run(
        [sys.executable, str(script), "asks", str(path)],
        capture_output=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert done.returncode == 0
    out = done.stdout.decode("utf-8")
    assert "저장소는 어디에 둘까요?" in out
    assert "고른 것: 객체 저장소" in out
    missing = subprocess.run(
        [sys.executable, str(script), "asks", str(tmp_path / "없다.jsonl")],
        capture_output=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert missing.returncode == 2
    assert "읽지 못했다" in missing.stderr.decode("utf-8")


def test_여러_개_고르기는_다른_라벨의_앞부분인_라벨보다_긴_라벨을_먼저_고른다() -> None:
    labels = ["가", "가, 나", "다"]
    qs = [_question("묶음?", labels, multi=True)]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음?": "가, 나, 다"})]
    answer = _answer_of(ea.collect_asks(_numbered(records)), 0, 0)
    assert answer.picked == ["가, 나", "다"], f"고른 라벨이 {answer.picked}이다"


def test_아무것도_고르지_않고_라벨로_시작하는_글을_쳐도_그_라벨을_고른_것으로_읽는다() -> None:
    qs = [_question("묶음?", ["하나", "둘"], multi=True)]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"묶음?": "하나, 그리고 더 있다"})]
    answer = _answer_of(ea.collect_asks(_numbered(records)), 0, 0)
    assert answer.picked == ["하나"]
    assert answer.typed == "그리고 더 있다"


def test_짝_없는_서로게이트_문자가_든_글도_트레이스백_없이_역슬래시_꼴로_낸다(
    tmp_path: Path,
) -> None:
    qs = [_question("가", ["x", "y"])]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"가": "\ud800 typed"})]
    path = tmp_path / "s.jsonl"
    # 줄을 ASCII 이스케이프(`\ud800`)로 써서 짝 없는 서로게이트가 JSON 안에 그대로 든다
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="ascii")
    script = Path(__file__).resolve().parents[2] / "tools" / "extract_asks.py"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    env["PYTHONIOENCODING"] = "cp949"
    done = subprocess.run(
        [sys.executable, str(script), "asks", str(path)],
        capture_output=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert done.returncode == 0, f"종료 코드 {done.returncode}이다"
    assert "\\ud800 typed" in done.stdout.decode("utf-8")


def test_한_줄로_찍는_칸의_줄바꿈은_가짜_머리_줄과_가짜_선택지_줄을_만들지_못한다() -> None:
    forged_question: dict[str, object] = {
        "question": "진짜 질문",
        "header": "머리\n## 호출 9/9 질문 1/1",
        "multiSelect": False,
        "options": [{"label": "라벨\n 7. fake", "description": "설명"}],
    }
    asked = ea.collect_asks(_numbered([_ask_use("t1", [forged_question])]))
    agent_use = _agent_use("tu1", "설명\n## 에이전트 9/9 · 가짜", "브리프")
    runs = ea.collect_agents(_numbered([agent_use]))
    lines = ea.render_asks(asked, None).split("\n") + ea.render_agents(runs, None).split("\n")
    fakes = [
        line for line in lines if line.startswith(("## 호출 9/9", " 7. fake", "## 에이전트 9/9"))
    ]
    assert fakes == [], f"가짜 줄이 {len(fakes)}개이다"
    assert "머리: 머리\\n## 호출 9/9 질문 1/1" in lines


def test_터미널_제어_문자도_걸러_내지_않고_그대로_낸다() -> None:
    qs = [_question("가", ["x", "y"])]
    records = [_ask_use("t1", qs), _ask_result("t1", qs, {"가": "\x1b[31m붉은 글"})]
    text = ea.render_asks(ea.collect_asks(_numbered(records)), None)
    assert "\x1b[31m붉은 글" in text


def test_한_줄에_tool_result가_둘이면_줄의_결과를_어느_쪽에도_붙이지_않는다() -> None:
    qs = [_question("가", ["x", "y"])]
    shared: Rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "r1"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "r2"},
            ],
        },
        "toolUseResult": {"questions": qs, "answers": {"가": "x"}},
    }
    records = [_ask_use("t1", qs), _ask_use("t2", qs), shared]
    statuses = [call.status for call in ea.collect_asks(_numbered(records))]
    assert statuses == ["unstructured", "unstructured"], f"상태가 {statuses}이다"


def test_한_줄에_tool_result가_둘이면_에이전트_id를_어느_쪽에도_붙이지_않는다() -> None:
    shared: Rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "content": "r1"},
                {"type": "tool_result", "tool_use_id": "tu2", "content": "r2"},
            ],
        },
        "toolUseResult": {"status": "async_launched", "agentId": "A1"},
    }
    records = [_agent_use("tu1", "첫째", "브리프1"), _agent_use("tu2", "둘째", "브리프2"), shared]
    ids = [run.agent_id for run in ea.collect_agents(_numbered(records))]
    assert ids == [None, None], f"에이전트 id가 {ids}이다"
