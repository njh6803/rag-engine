"""판정 파일 `judgments.jsonl`의 읽기와 쓰기(티켓 search-eval 12, 명세 "LLM 관련성 판정").

줄 하나가 판정 하나이고 칸은 `query_sha256`, `text_sha256`, `relevant`, `model`, `prompt_version`,
`judged_at`(날짜) 여섯이다. 글은 없다. 칸이 모자라거나 남거나 형이 다른 줄은 받지 않고 줄 번호만
알린다. 줄의 내용은 오류 문장에 싣지 않는다.

쓰는 길은 셋이다. `append_judgment`가 판정 하나를 받을 때마다 파일 끝에 줄을 덧붙인다(끊긴 실행을
다시 돌리면 이미 받은 조합을 건너뛰게 하려는 것이다). `rewrite_sorted`가 끝나면 열쇠 순으로 정렬해
다시 쓰고(같은 열쇠가 둘이면 나중 줄이 이긴다), `prune_judgments`가 지금의 모델과 지시문의 판에 맞지
않는 줄을 지운다. 다시 쓰기는 임시 파일에 쓴 뒤 바꾼다. 쓰다 끊겨도 옛 파일이 남는다.

경로는 묶음의 경로 판정(`BundlePaths`)을 지난다. 링크를 푼 결과가 묶음 밖이면 읽지도 쓰지도 않는다.
못 보는 것. 판정한 뒤 열기까지 사이에 링크가 바뀌는 경쟁은 막지 않는다(`BundlePaths`와 같다).
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Final

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.app.eval_judgments import JUDGMENTS_FILE, Judgment
from rag_engine.domain.entities import JsonValue

_FIELDS: Final = (
    "query_sha256",
    "text_sha256",
    "relevant",
    "model",
    "prompt_version",
    "judged_at",
)


class JudgmentFileError(Exception):
    """판정 파일의 줄이 형식에 맞지 않는다. 메시지는 줄 번호만 싣는다."""


def judgments_path(paths: BundlePaths) -> Path:
    """묶음 안의 판정 파일 경로. 파일이 없어도 풀린다. 묶음 밖을 가리키면 `BundlePathError`다."""
    return paths.resolve(JUDGMENTS_FILE)


def read_judgments(path: Path) -> list[Judgment] | None:
    """모든 줄을 읽는다. 파일이 없으면 `None`이다. 빈 줄은 건너뛴다."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    judgments: list[Judgment] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            judgments.append(_parse(line, number))
    return judgments


def append_judgment(path: Path, judgment: Judgment) -> None:
    """파일 끝에 줄 하나를 덧붙인다. 파일이 없으면 만든다."""
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_dump(judgment))


def rewrite_sorted(path: Path) -> None:
    """열쇠 순으로 정렬해 다시 쓴다. 같은 열쇠가 둘이면 나중 줄이 이긴다. 파일이 없으면 아무것도
    하지 않는다."""
    judgments = read_judgments(path)
    if judgments is None:
        return
    _replace(path, list({judgment.key: judgment for judgment in judgments}.values()))


def prune_judgments(path: Path, *, model: str, prompt_version: str) -> int:
    """`model`과 `prompt_version`이 지금의 것이 아닌 줄을 지우고 지운 줄의 수를 낸다. 지울 줄이
    없으면 파일을 고치지 않는다. 파일이 없으면 0이다."""
    judgments = read_judgments(path)
    if judgments is None:
        return 0
    kept = [
        judgment
        for judgment in judgments
        if judgment.model == model and judgment.prompt_version == prompt_version
    ]
    removed = len(judgments) - len(kept)
    if removed:
        _replace(path, kept)
    return removed


def _replace(path: Path, judgments: list[Judgment]) -> None:
    """열쇠 순으로 정렬한 줄을 임시 파일에 쓰고 파일을 바꾼다. 앞서 끊긴 실행이 남긴 임시
    파일(링크일 수도 있다)은 먼저 지운다. 지우지 않으면 쓰기가 링크를 따라 묶음 밖의 파일을
    덮는다."""
    ordered = sorted(judgments, key=lambda judgment: judgment.key)
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    temporary.write_text(
        "".join(_dump(judgment) for judgment in ordered), encoding="utf-8", newline="\n"
    )
    os.replace(temporary, path)


def _dump(judgment: Judgment) -> str:
    values: dict[str, JsonValue] = {
        "query_sha256": judgment.query_sha256,
        "text_sha256": judgment.text_sha256,
        "relevant": judgment.relevant,
        "model": judgment.model,
        "prompt_version": judgment.prompt_version,
        "judged_at": judgment.judged_at.isoformat(),
    }
    return json.dumps(values, ensure_ascii=False) + "\n"


def _parse(line: str, number: int) -> Judgment:
    problem = JudgmentFileError(f"{JUDGMENTS_FILE}의 {number}번째 줄이 형식에 맞지 않는다")
    try:
        value: JsonValue = json.loads(line)
    except json.JSONDecodeError:
        raise problem from None
    if not isinstance(value, dict) or set(value) != set(_FIELDS):
        raise problem
    query, text = value["query_sha256"], value["text_sha256"]
    relevant, model = value["relevant"], value["model"]
    version, judged_at = value["prompt_version"], value["judged_at"]
    if not (
        isinstance(query, str)
        and isinstance(text, str)
        and isinstance(relevant, bool)
        and isinstance(model, str)
        and isinstance(version, str)
        and isinstance(judged_at, str)
    ):
        raise problem
    try:
        day = date.fromisoformat(judged_at)
    except ValueError:
        raise problem from None
    return Judgment(
        query_sha256=query,
        text_sha256=text,
        relevant=relevant,
        model=model,
        prompt_version=version,
        judged_at=day,
    )
