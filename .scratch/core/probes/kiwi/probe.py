"""kiwipiepy 가 한국어·영어·숫자가 섞인 글을 어떤 토큰과 품사로 내는지 본다(ADR 0006, 명세).

ADR 0006 은 키워드 색인의 형태소 분석을 앱의 kiwipiepy 에 맡기고 그 토큰을
`to_tsvector('simple', …)` 에 넣는다고 정했다. 어느 품사의 토큰을 키워드로 넣을지, 복합 명사가
어떻게 갈리는지, 문장 경계를 어떻게 자를지(청킹의 문장 경계)는 명세가 정한다. 이 프로브는 그 결정의
입력으로 표본 글의 토큰 목록과 `split_into_sents` 의 결과, 설치되는 판(kiwipiepy, kiwipiepy_model)을
찍는다.

실행(저장소 루트에서. 모델 패키지(kiwipiepy_model)가 함께 설치된다. 네트워크는 PyPI 만):
    uv run --with kiwipiepy==0.24.1 python -I -X utf8 .scratch/core/probes/kiwi/probe.py
출력은 `probe_out.txt` 로 남겼다(2026-11-10). 다섯째 표본은 넷째 표본의 끝 구두점을 공백으로 뗀
것이다(명세의 전처리 규칙: 라틴 글자·숫자 뒤에 붙은 ASCII 문장 부호를 떼면 `search.` 가
`s/SL earch./SL` 로 갈리던 것이 고쳐지는지 본다).
"""

from __future__ import annotations

import importlib.metadata
import time

from kiwipiepy import Kiwi, Sentence, Token

SAMPLES = [
    "설치형 문서 검색 서버는 PostgreSQL 18과 pgvector 0.8.7을 씁니다.",
    "지식베이스마다 임베딩 모델을 고를 수 있고, 리랭커는 bge-reranker-v2-m3입니다. 다음 문장",
    "제3조(정의) 이 규정에서 사용하는 용어의 뜻은 다음과 같다. 1. “문서”란 기록물을 말한다.",
    "Hybrid search combines BM25-style keyword matching with HNSW vector search.",
    "Hybrid search combines BM25-style keyword matching with HNSW vector search .",
]


def main() -> None:
    for pkg in ("kiwipiepy", "kiwipiepy_model"):
        print(pkg, importlib.metadata.version(pkg))
    t0 = time.perf_counter()
    kiwi = Kiwi()
    print(f"Kiwi() init {time.perf_counter() - t0:.2f}s")
    for text in SAMPLES:
        print("===", text)
        # 스텁의 반환형이 문자열 입력과 문자열 목록 입력의 합집합이라 Token 인 것만 고른다.
        tokens = [t for t in kiwi.tokenize(text, normalize_coda=True) if isinstance(t, Token)]
        print("  tokens:", " ".join(f"{t.form}/{t.tag}" for t in tokens))
        print("  spans:", " ".join(f"{t.start}+{t.len}" for t in tokens))
        sents = [s for s in kiwi.split_into_sents(text) if isinstance(s, Sentence)]
        print("  sentences:", [s.text for s in sents])


if __name__ == "__main__":
    main()
