"""Kiwi 형태소 분석기 어댑터: 키워드 토큰과 문장 분리(명세 "키워드 토큰", ADR 0006).

조각과 질의가 같은 함수(`tokenize_keywords`)를 지나야 같은 토큰을 낸다. 규칙(품사 집합, 전처리,
`normalize_coda`)의 판은 `index_elements.KEYWORD_RULES_VERSION`이고, 규칙을 바꾸면 그 상수를 올려
토크나이저 판이 달라지게 한다. 문장 분리는 청킹이 문장 경계를 얻는 자리이고 그 판은 설치된
kiwipiepy의 판이다(`index_elements`가 청킹 해시에 넣는다).
"""

import re
from functools import cache
from typing import Final

from kiwipiepy import Kiwi

# 키워드로 넣는 품사 태그: 일반 명사, 고유 명사, 수사, 외국어, 한자, 숫자, 어근, 그리고 Kiwi가 한
# 덩이로 내는 웹 형식 넷. 동사·형용사 어간, 조사, 어미, 의존 명사, 대명사, 기호는 넣지 않는다.
_KEYWORD_TAGS: Final = frozenset(
    {"NNG", "NNP", "NR", "SL", "SH", "SN", "XR", "W_URL", "W_EMAIL", "W_HASHTAG", "W_SERIAL"}
)

_FOREIGN_TAG: Final = "SL"

# 라틴 글자·숫자 뒤에 붙고 그 뒤가 라틴 글자·숫자나 `/`로 이어지지 않는 ASCII 문장 부호. 영어 문장
# 끝의 `search.`가 `s/SL earch./SL`로 갈리던 것을 막는다(프로브 `kiwi/probe_out.txt`). `0.8.7`처럼
# 낱말 안에서 뒤가 이어지는 부호와, 웹 주소의 `https://`처럼 `/`가 뒤따르는 콜론은 그대로 둔다.
_ATTACHED_PUNCTUATION: Final = re.compile(r"(?<=[0-9A-Za-z])[.,;:!?]+(?![0-9A-Za-z/])")


@cache
def _kiwi() -> Kiwi:
    # 모델을 읽는 데 1초쯤 걸려 프로세스마다 한 번만 만든다(프로브 `kiwi/probe_out.txt`).
    return Kiwi()


def tokenize_keywords(text: str) -> list[str]:
    """글에서 키워드 토큰을 글 순서대로 뽑는다. 외국어 토큰은 소문자로 바꾼다."""
    prepared = _ATTACHED_PUNCTUATION.sub(" ", text)
    tokens = _kiwi().tokenize(prepared, normalize_coda=True)
    return [
        token.form.lower() if token.tag == _FOREIGN_TAG else token.form
        for token in tokens
        if token.tag in _KEYWORD_TAGS
    ]


def split_sentences(text: str) -> list[str]:
    """글을 문장으로 나눈다. 문장 글은 원문의 구간 그대로다."""
    return [text[sentence.start : sentence.end] for sentence in _kiwi().split_into_sents(text)]
