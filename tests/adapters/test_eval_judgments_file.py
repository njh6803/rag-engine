"""판정 파일 `judgments.jsonl`의 읽기와 쓰기(티켓 search-eval 12, 명세 "LLM 관련성 판정").

줄 하나가 판정 하나이고 칸은 여섯이다(글은 없다). 쓰는 길은 셋이다. 판정 하나를 받을 때마다 끝에
덧붙이고, 끝나면 열쇠 순으로 정렬해 다시 쓰고, `--prune`이 맞지 않는 줄을 지운다. 경로는 묶음의 경로
판정(`BundlePaths`)을 지난다.
"""

import json
from datetime import date
from pathlib import Path

import pytest
from tests.support.eval_bundle import make_folder_link

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.eval_judgments_file import (
    JudgmentFileError,
    append_judgment,
    judgments_path,
    prune_judgments,
    read_judgments,
    rewrite_sorted,
)
from rag_engine.app.eval_judgments import Judgment

MODEL = "claude-test"


def _judgment(
    query: str, *, relevant: bool = True, model: str = MODEL, version: str = "1"
) -> Judgment:
    return Judgment(
        query_sha256=query,
        text_sha256="t",
        relevant=relevant,
        model=model,
        prompt_version=version,
        judged_at=date(2026, 11, 14),
    )


def test_파일이_없으면_없다고_낸다(tmp_path: Path) -> None:
    assert read_judgments(tmp_path / "judgments.jsonl") is None


def test_덧붙인_줄은_여섯_칸이고_읽으면_같은_판정이_나온다(tmp_path: Path) -> None:
    path = tmp_path / "judgments.jsonl"
    first, second = _judgment("b"), _judgment("a", relevant=False)

    append_judgment(path, first)
    append_judgment(path, second)

    assert read_judgments(path) == [first, second]
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row == {
        "query_sha256": "b",
        "text_sha256": "t",
        "relevant": True,
        "model": MODEL,
        "prompt_version": "1",
        "judged_at": "2026-11-14",
    }


@pytest.mark.parametrize(
    "line",
    [
        "{깨진 줄",
        "[1, 2]",
        '{"query_sha256": "a"}',
        '{"query_sha256": "a", "text_sha256": "t", "relevant": "yes", "model": "m",'
        ' "prompt_version": "1", "judged_at": "2026-11-14"}',
        '{"query_sha256": "a", "text_sha256": "t", "relevant": true, "model": "m",'
        ' "prompt_version": "1", "judged_at": "내일"}',
        '{"query_sha256": "a", "text_sha256": "t", "relevant": true, "model": "m",'
        ' "prompt_version": "1", "judged_at": "2026-11-14", "extra": 1}',
    ],
    ids=[
        "JSON이 아니다",
        "객체가 아니다",
        "칸이 빠졌다",
        "참거짓이 아니다",
        "날짜가 아니다",
        "칸이 남는다",
    ],
)
def test_형식이_맞지_않는_줄은_줄_번호만_알리고_내용은_싣지_않는다(
    tmp_path: Path, line: str
) -> None:
    path = tmp_path / "judgments.jsonl"
    append_judgment(path, _judgment("a"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")

    with pytest.raises(JudgmentFileError) as caught:
        read_judgments(path)

    assert "2번째 줄" in str(caught.value)
    assert line not in str(caught.value)


def test_정렬해_다시_쓰면_열쇠_순이고_같은_열쇠는_나중_줄이_이긴다(tmp_path: Path) -> None:
    path = tmp_path / "judgments.jsonl"
    for judgment in (_judgment("b"), _judgment("a", relevant=False), _judgment("a", relevant=True)):
        append_judgment(path, judgment)

    rewrite_sorted(path)

    assert read_judgments(path) == [_judgment("a", relevant=True), _judgment("b")]


def test_임시_파일이_밖을_가리키는_링크여도_따라가_쓰지_않는다(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("그대로", encoding="utf-8")
    (bundle / "judgments.jsonl.tmp").symlink_to(outside)
    path = bundle / "judgments.jsonl"
    append_judgment(path, _judgment("a"))

    rewrite_sorted(path)

    assert outside.read_text(encoding="utf-8") == "그대로"
    assert read_judgments(path) == [_judgment("a")]


def test_정렬해_다시_쓸_때_파일이_없으면_아무것도_만들지_않는다(tmp_path: Path) -> None:
    rewrite_sorted(tmp_path / "judgments.jsonl")

    assert not (tmp_path / "judgments.jsonl").exists()


def test_prune은_지금의_모델과_지시문_판에_맞지_않는_줄만_지우고_지운_수를_낸다(
    tmp_path: Path,
) -> None:
    path = tmp_path / "judgments.jsonl"
    keep = _judgment("a")
    for judgment in (_judgment("b", model="다른-모델"), keep, _judgment("c", version="0")):
        append_judgment(path, judgment)

    removed = prune_judgments(path, model=MODEL, prompt_version="1")

    assert removed == 2
    assert read_judgments(path) == [keep]


def test_prune은_지울_줄이_없으면_파일을_고치지_않는다(tmp_path: Path) -> None:
    path = tmp_path / "judgments.jsonl"
    append_judgment(path, _judgment("b"))
    append_judgment(path, _judgment("a"))
    before = path.read_bytes()

    assert prune_judgments(path, model=MODEL, prompt_version="1") == 0

    assert path.read_bytes() == before


def test_경로는_묶음_밖을_가리키는_링크이면_거부한다(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    make_folder_link(bundle / "judgments.jsonl", outside)

    with pytest.raises(BundlePathError):
        judgments_path(BundlePaths(bundle))


def test_경로는_묶음_안의_judgments_jsonl이다(tmp_path: Path) -> None:
    assert judgments_path(BundlePaths(tmp_path)) == tmp_path.resolve() / "judgments.jsonl"
