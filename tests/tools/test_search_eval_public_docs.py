"""커밋된 공공 문서 묶음 `evals/public-docs/`의 저장소 상태 시험(티켓 search-eval 10, 명세 Testing
Decisions의 "저장소 상태의 시험").

하나는 지금 통과함을 재는 시험이다. 묶음이 `validate`의 파일 검사(형식, 해시, 용량, 기록의 판과
크기와 요청 지문)를 지나야 한다. 다른 하나는 위반을 잡는 변이 시험이다. 묶음을 임시 폴더에
복사해 한 곳을 어기면 같은 검사가 그것을 까닭과 함께 잡아야 한다. 훑은 범위가 비면 위반 0으로
조용히 초록이므로 문서와 기대 근거와 기록 파일의 수가 비지 않은 것도 함께 본다.

색인이 필요한 검사(글귀가 문서의 본문에 있는지)와 평가는 pytest가 아니라 CI의 게이트가 본다.
실제 모델과 색인된 데이터베이스가 필요하기 때문이다(명세).
"""

import json
import shutil
from pathlib import Path

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_set_reader import read_eval_set
from rag_engine.adapters.eval_validate import validate_bundle

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE = ROOT / "evals" / "public-docs"
COMPOSE = ROOT / "compose.eval.yml"
RECORDS = (
    "records.json",
    "chunk-embeddings.keys",
    "chunk-embeddings.f32",
    "query-embeddings.keys",
    "query-embeddings.f32",
    "rerank.jsonl",
)


def _copy_bundle(target: Path) -> Path:
    copy = target / "public-docs"
    shutil.copytree(BUNDLE, copy)
    return copy


def test_이_저장소의_공공_문서_묶음은_파일_검사를_지난다() -> None:
    problems = validate_bundle(BUNDLE, COMPOSE)

    assert problems == (), "\n".join(f"{problem.where}: {problem.reason}" for problem in problems)


def test_이_저장소의_공공_문서_묶음은_비어_있지_않다() -> None:
    eval_set = read_eval_set(BundlePaths(BUNDLE))

    assert len(eval_set.documents) >= 40
    assert len(eval_set.evidence) >= 140
    assert [len(query_list.queries) >= 140 for query_list in eval_set.query_lists] == [True, True]
    for name in RECORDS:
        assert (BUNDLE / "records" / name).stat().st_size > 0, name


def test_문서_파일의_내용이_목록의_해시와_다르면_파일_검사가_잡는다(tmp_path: Path) -> None:
    copy = _copy_bundle(tmp_path)
    victim = next((copy / "documents" / "laws").iterdir())
    victim.write_bytes(victim.read_bytes() + b"\n")

    problems = validate_bundle(copy, COMPOSE)

    assert any(
        problem.where.endswith(victim.name) and "해시" in problem.reason for problem in problems
    )


def test_기대_근거가_목록에_없는_문서를_가리키면_파일_검사가_잡는다(tmp_path: Path) -> None:
    copy = _copy_bundle(tmp_path)
    entry = {
        "id": "x-없는문서",
        "evidence": [
            {"kind": "passage", "document": "laws/없는문서.pdf", "passage": "목록에 없는 문서다"}
        ],
        "tags": [],
    }
    with (copy / "evidence.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    problems = validate_bundle(copy, COMPOSE)

    assert any(
        problem.where == "기대 근거 x-없는문서"
        and "문서 목록에 없는 문서 laws/없는문서.pdf" in problem.reason
        for problem in problems
    )


def test_추론_기록의_판이_구성과_다르면_파일_검사가_잡는다(tmp_path: Path) -> None:
    copy = _copy_bundle(tmp_path)
    manifest = copy / "records" / "records.json"
    text = manifest.read_text(encoding="utf-8")
    assert '"1.9.4"' in text
    manifest.write_text(text.replace('"1.9.4"', '"1.9.3"'), encoding="utf-8")

    problems = validate_bundle(copy, COMPOSE)

    assert any("tei_version 1.9.3이 config.json의 1.9.4과 다르다" in p.reason for p in problems)
