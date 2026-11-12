from rag_engine.domain.index_text import (
    compose_index_text,
    fit_section,
    section_candidates,
    section_line,
    section_token_limit,
)


def test_절_경로는_꺽쇠로_이은_한_줄이다() -> None:
    assert section_line(["제3조", "정의"]) == "제3조 > 정의"


def test_절_경로_줄_뒤에_빈_줄을_두고_조각_글을_붙인다() -> None:
    assert compose_index_text(["제3조", "정의"], "본문") == "제3조 > 정의\n\n본문"


def test_절_경로가_비면_조각_글만_낸다() -> None:
    assert compose_index_text([], "본문") == "본문"


def test_절_경로가_하나면_구분자가_들지_않는다() -> None:
    assert compose_index_text(["서문"], "본문") == "서문\n\n본문"


def test_절_경로_후보는_바깥_제목부터_하나씩_뺀_줄이다() -> None:
    assert section_candidates(("제3조", "정의", "용어")) == [
        "제3조 > 정의 > 용어",
        "정의 > 용어",
        "용어",
    ]


def test_절_경로_줄의_토큰_상한은_조각_상한의_4분의_1이다() -> None:
    assert section_token_limit(512) == 128
    assert section_token_limit(64) == 16


def _tokens(full: tuple[str, ...], *counts: int) -> dict[str, int]:
    return dict(zip(section_candidates(full), counts, strict=True))


def test_절_경로가_상한_안이면_그대로_남긴다() -> None:
    full = ("제3조", "정의")

    assert fit_section(full, 64, _tokens(full, 16, 8)) == full


def test_절_경로가_상한을_넘으면_상한_안이_될_때까지_바깥_제목부터_뺀다() -> None:
    full = ("제3조", "정의", "용어")

    assert fit_section(full, 64, _tokens(full, 40, 17, 5)) == ("용어",)
    assert fit_section(full, 64, _tokens(full, 40, 16, 5)) == ("정의", "용어")


def test_안쪽_제목_하나는_상한을_넘어도_늘_남는다() -> None:
    full = ("제3조", "정의")

    assert fit_section(full, 64, _tokens(full, 90, 40)) == ("정의",)


def test_절_경로가_비면_빈_경로를_낸다() -> None:
    assert fit_section((), 64, {}) == ()
