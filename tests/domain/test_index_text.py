from rag_engine.domain.index_text import compose_index_text, section_line


def test_절_경로는_꺽쇠로_이은_한_줄이다() -> None:
    assert section_line(["제3조", "정의"]) == "제3조 > 정의"


def test_절_경로_줄_뒤에_빈_줄을_두고_조각_글을_붙인다() -> None:
    assert compose_index_text(["제3조", "정의"], "본문") == "제3조 > 정의\n\n본문"


def test_절_경로가_비면_조각_글만_낸다() -> None:
    assert compose_index_text([], "본문") == "본문"


def test_절_경로가_하나면_구분자가_들지_않는다() -> None:
    assert compose_index_text(["서문"], "본문") == "서문\n\n본문"
