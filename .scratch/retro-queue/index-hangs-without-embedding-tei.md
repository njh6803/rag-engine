# index-hangs-without-embedding-tei: 임베딩 TEI가 꺼진 채 `search_eval.py index`를 돌리면 오류 문장 없이 46분 넘게 재시도 대기로 보인다

**상태:** 열림
**어디로:** `src/rag_engine/adapters/eval_index.py`의 `index_bundle`(시작할 때 환경의 `RAG_EVAL_EMBEDDING_URL`이 가리키는 끝점의 건강 확인을 한 번 하고, 응답이 없으면 환경 변수 이름만 싣는 문장으로 종료 코드 2로 끝낸다. 문장에 URL 값은 싣지 않는다. 시험은 `tests/adapters/`에서 끝점이 닫힌 경우를 본다)
**승인:** 자체 승인 2026-11-16, 1회차(고침이라 추가 기준 횟수를 보지 않고 반영한다. 이 세션의 PR은 문서와 프로브뿐이라 코드 변경은 싣지 않고 대기열에 둔다), 일지 2026-11-16-1341-search-eval-18-min-score-distribution.md, ADR 불필요

티켓 18 세션이 `--records read`로 `index`를 돌렸는데 임베딩 TEI(18083)가 꺼져 있었다. 청킹이 토큰 세기를 TEI의 `/tokenize`에 묻고 그 호출은 추론 기록에 없어서(명세가 이미 적었다) 읽기 방식에서도 임베딩 끝점이 살아 있어야 한다. 그런데 작업 46개가 `embedding_unavailable`로 재시도 대기에 들어갔고(데이터베이스의 `jobs` 표를 손으로 봤다) 명령은 46분 넘게 오류 문장 없이 돌았다. 세션이 `jobs` 표를 열어 보고서야 원인을 알았다. 처방은 시작할 때 한 번 끝점을 확인하는 사전 조건이다. `check_ready`는 데이터베이스와 묶음만 보고 끝점은 보지 않는다.
