"""Kiwi 키워드 토크나이저와 문장 분리(명세 "키워드 토큰", "청킹과 토큰 세기")."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from kiwipiepy import Kiwi

from rag_engine.adapters import kiwi as kiwi_module
from rag_engine.adapters.index_elements import KEYWORD_RULES_VERSION
from rag_engine.adapters.kiwi import split_sentences, tokenize_keywords


def test_늘어진_받침은_정규화해_본래_낱말로_센다() -> None:
    # 받침 정규화를 끄면 "하이닼"이 한 낱말로 남아 "하이다"를 찾는 질의가 비껴간다.
    assert tokenize_keywords("하이닼ㅋㅋ") == ["하이다"]


def test_키워드_규칙_판_1의_표본은_고정된_토큰을_낸다() -> None:
    # 이 표본이 달라지면 키워드 규칙이 바뀐 것이다. 규칙을 바꾸면 `KEYWORD_RULES_VERSION`을 올리고
    # 이 표본의 기대를 새 판 것으로 고친다(토크나이저 판이 달라져 "재색인 필요"로 드러난다).
    assert KEYWORD_RULES_VERSION == "1"
    text = "설치형 문서 검색 서버는 PostgreSQL 18과 pgvector 0.8.7을 씁니다."

    assert tokenize_keywords(text) == [
        "설치",
        "문서",
        "검색",
        "서버",
        "postgresql",
        "18",
        "pgvector",
        "0.8.7",
    ]


def test_동사_어간과_조사와_어미는_키워드에_넣지_않는다() -> None:
    assert tokenize_keywords("문서를 찾는다") == ["문서"]


def test_외국어_토큰은_소문자로_바꾼다() -> None:
    assert tokenize_keywords("Hybrid HNSW Search") == ["hybrid", "hnsw", "search"]


def test_웹_형식_토큰은_한_덩이로_넣고_대소문자를_그대로_둔다() -> None:
    tokens = tokenize_keywords("https://example.com/a.b 와 Name@Example.com 과 #태그")

    assert tokens == ["https://example.com/a.b", "Name@Example.com", "#태그"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("vector search.", ["vector", "search"]),
        ("Hybrid search works.다음 문장", ["hybrid", "search", "works", "다음", "문장"]),
        ("v2.0. 이다", ["v", "2.0"]),
        ("a, b; c: d! e?", ["a", "b", "c", "d", "e"]),
    ],
    ids=["문장_끝_마침표", "마침표_뒤_한글", "숫자_뒤_마침표", "여러_부호"],
)
def test_라틴_글자와_숫자_뒤에_붙은_문장_부호는_떼고_토큰을_가른다(
    text: str, expected: list[str]
) -> None:
    assert tokenize_keywords(text) == expected


def test_낱말_안의_마침표는_떼지_않는다() -> None:
    assert tokenize_keywords("버전 0.8.7 e.g. 이다") == ["버전", "0.8.7", "e.g"]


def test_복합_명사는_질의와_조각에서_같은_토큰으로_갈린다() -> None:
    query = tokenize_keywords("지식베이스")
    chunk = tokenize_keywords("이 지식베이스를 설치한다")

    assert query == ["지식", "베이스"]
    assert set(query) <= set(chunk)


def test_토큰이_없는_글은_빈_목록을_낸다() -> None:
    assert tokenize_keywords("") == []
    assert tokenize_keywords("... !!!") == []


def test_문장을_원문의_구간_그대로_나눈다() -> None:
    text = "첫째 문장입니다. 둘째 문장입니다!  셋째?"

    assert split_sentences(text) == ["첫째 문장입니다.", "둘째 문장입니다!", "셋째?"]


def test_빈_글은_문장이_없다() -> None:
    assert split_sentences("") == []
    assert split_sentences("  \n ") == []


def test_타입_스텁이_적은_모양을_실제_kiwi가_낸다() -> None:
    # `typings/kiwipiepy/__init__.pyi`는 문자열 하나를 주면 `list[Token]`과 `list[Sentence]`가
    # 돌아온다고 적는다. kiwipiepy를 올린 뒤에도 그런지 본다.
    kiwi = Kiwi()
    text = "문서를 찾는다. 다음 문장"

    tokens = kiwi.tokenize(text, normalize_coda=True)
    sentences = kiwi.split_into_sents(text)

    assert [token.form for token in tokens][:2] == ["문서", "를"]
    assert all(
        isinstance(token.tag, str) and isinstance(token.start, int) and isinstance(token.len, int)
        for token in tokens
    )
    assert [text[s.start : s.end] for s in sentences] == [s.text for s in sentences]
    assert len(sentences) == 2


def test_여러_스레드가_불러도_Kiwi는_한_번에_하나만_쓴다(monkeypatch: pytest.MonkeyPatch) -> None:
    # kiwipiepy의 스레드 안전성을 확인하지 못했다. 서버의 예열 스레드와 첫 검색이 겹쳐도 같은
    # 인스턴스를 동시에 쓰지 않아야 한다.
    guard = threading.Lock()
    inside = [0, 0]  # 지금 안에 든 호출 수, 가장 많았던 호출 수

    class _SlowKiwi:
        def _enter(self) -> list[object]:
            with guard:
                inside[0] += 1
                inside[1] = max(inside)
            time.sleep(0.05)
            with guard:
                inside[0] -= 1
            return []

        def tokenize(self, _text: str, *, normalize_coda: bool) -> list[object]:
            return self._enter()

        def split_into_sents(self, _text: str) -> list[object]:
            return self._enter()

    slow = _SlowKiwi()
    monkeypatch.setattr(kiwi_module, "_kiwi", lambda: slow)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(tokenize_keywords, "글"), pool.submit(split_sentences, "글")] * 2
        for future in futures:
            future.result()

    assert inside[1] == 1
