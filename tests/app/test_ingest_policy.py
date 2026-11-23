"""수집 정책의 단위 시험. 키와 패턴의 짝을 표로 늘어놓고 맞고 안 맞는 것을 본다."""

import unicodedata

import pytest

from rag_engine.app.ingest_policy import RejectReason, matches_exclude, reject_reason

_MAX = 100


@pytest.mark.parametrize(
    "key",
    [
        ".숨김.pdf",
        "폴더/.숨김.pdf",
        ".git/설계.pdf",
        "a/.cache/b/설계.docx",
        "~$보고서.docx",
        "폴더/~$보고서.docx",
    ],
)
def test_숨김_토막과_오피스_임시_파일은_패턴이_없어도_제외된다(key: str) -> None:
    assert matches_exclude(key, [])


@pytest.mark.parametrize("key", ["폴더/~$보고서/설계.docx", "설계~$.docx", "a~$/b.pdf"])
def test_틸드_달러는_마지막_토막의_맨_앞일_때만_제외된다(key: str) -> None:
    assert not matches_exclude(key, [])


@pytest.mark.parametrize(
    ("key", "pattern", "expected"),
    [
        ("임시/설계.pdf", "임시", True),
        ("a/임시/b/설계.pdf", "임시", True),
        ("임시본/설계.pdf", "임시", False),
        ("a/b_초안.docx", "*_초안.docx", True),
        ("b_초안.docx", "*_초안.docx", True),
        ("a/b_초안.pdf", "*_초안.docx", False),
        ("a/보고서1.pdf", "보고서?.pdf", True),
        ("a/보고서12.pdf", "보고서?.pdf", False),
        ("a/보고서.pdf", "보고서?.pdf", False),
        ("a/b/c.pdf", "a/*.pdf", False),
        ("a/c.pdf", "a/*.pdf", True),
        ("a/b/c.pdf", "a/**", True),
        ("a/b/c.pdf", "a/**.pdf", True),
        ("x/a/b/c.pdf", "a/**", False),
        ("a/b/c.pdf", "**/c.pdf", True),
        ("c.pdf", "**/c.pdf", False),
        ("a/b/c.pdf", "a/?/c.pdf", True),
        ("a/bb/c.pdf", "a/?/c.pdf", False),
        ("a/b/c.pdf", "a/b/c.pdf", True),
        ("A/설계.PDF", "a/*.pdf", False),
        ("임시/설계.pdf", "임시/", False),
        ("a/[b].pdf", "[b].pdf", True),
        ("a/b.pdf", "[b].pdf", False),
        ("a/b.pdf", "a/*.pdf?", False),
    ],
)
def test_제외_패턴은_glob_뜻대로_토막이나_키_전체에_맞는다(
    key: str, pattern: str, *, expected: bool
) -> None:
    assert matches_exclude(key, [pattern]) is expected


def test_제외_패턴은_대소문자를_가린다() -> None:
    assert matches_exclude("Draft/설계.pdf", ["Draft"])
    assert not matches_exclude("draft/설계.pdf", ["Draft"])


def test_패턴이_여럿이면_하나라도_맞으면_제외된다() -> None:
    assert matches_exclude("b/설계.pdf", ["a", "b"])
    assert not matches_exclude("c/설계.pdf", ["a", "b"])


def test_별이_길게_이어진_패턴도_빠르게_맞춘다() -> None:
    assert not matches_exclude("a" * 200 + ".pdf", ["*" * 50 + "z"])


def test_풀어_적은_한글_폴더에도_합쳐_적은_패턴이_맞는다() -> None:
    decomposed_key = unicodedata.normalize("NFD", "임시/규정.docx")
    assert decomposed_key != "임시/규정.docx"
    matched = matches_exclude(decomposed_key, ["임시"])
    assert matched, f"받은 값: {matched}"
    assert matches_exclude("임시/규정.docx", [unicodedata.normalize("NFD", "임시")])


def test_별_사이에_같은_글자가_끼어도_지수_시간으로_느려지지_않는다() -> None:
    # 정규식으로 옮기면 되짚기가 글자 수에 대해 지수로 늘어 작업자가 멈춘다.
    pattern = "*a" * 12 + "*b"
    assert not matches_exclude("a" * 60 + ".pdf", [pattern])
    assert matches_exclude("a" * 60 + "b", [pattern])


@pytest.mark.parametrize("key", ["설계.pdf", "설계.PDF", "설계.Docx", "a/b/설계.HWPX", "a.b.hwpx"])
def test_지원하는_확장자는_대소문자와_상관없이_통과한다(key: str) -> None:
    assert reject_reason(key, 1, exclude_patterns=[], max_bytes=_MAX) is None


@pytest.mark.parametrize(
    "key", ["설계.txt", "설계", "설계.pdf.bak", "설계.doc", "a/pdf", "설계.pdfx"]
)
def test_지원하지_않는_확장자는_unsupported_type이다(key: str) -> None:
    reason = reject_reason(key, 1, exclude_patterns=[], max_bytes=_MAX)

    assert reason is RejectReason.UNSUPPORTED_TYPE


def test_크기가_상한과_같으면_받고_넘으면_too_large다() -> None:
    assert reject_reason("설계.pdf", _MAX, exclude_patterns=[], max_bytes=_MAX) is None
    over = reject_reason("설계.pdf", _MAX + 1, exclude_patterns=[], max_bytes=_MAX)
    assert over is RejectReason.TOO_LARGE


def test_크기를_모르면_크기로는_거르지_않는다() -> None:
    assert reject_reason("설계.pdf", None, exclude_patterns=[], max_bytes=_MAX) is None


def test_제외가_형식보다_먼저_걸린다() -> None:
    reason = reject_reason(".숨김.txt", _MAX + 1, exclude_patterns=[], max_bytes=_MAX)

    assert reason is RejectReason.EXCLUDED


def test_패턴에_걸린_큰_파일은_excluded로_센다() -> None:
    reason = reject_reason("임시/설계.pdf", _MAX + 1, exclude_patterns=["임시"], max_bytes=_MAX)

    assert reason is RejectReason.EXCLUDED


def test_형식이_크기보다_먼저_걸린다() -> None:
    reason = reject_reason("설계.txt", _MAX + 1, exclude_patterns=[], max_bytes=_MAX)

    assert reason is RejectReason.UNSUPPORTED_TYPE
