# 06: TEI 어댑터, Kiwi 키워드, 구조 우선 청킹

**What to build:** 문서 글을 조각으로 자르고, 임베딩 서버로 토큰을 세고 벡터를 만들며, 한국어 키워드 토큰을 뽑는 부품이 포트 뒤에 선다. 작업자와 검색(07)이 이 부품을 조립하므로, 이 티켓은 각 부품의 시험(명세의 보조 이음매)으로 끝까지 확인한다. 데이터베이스가 필요 없어 04·05와 나란히 돈다. 03 뒤에 도는 것은 판 요소의 상수 둘(전략 구현 판, 키워드 규칙 판)을 03이 한 자리에 두고 이 티켓이 그 이름을 쓰기 때문이다.

**Blocked by:** 03 (`migrate`와 판 요소)

**Status:** done

**03이 넘긴 것:** 판의 상수 둘은 `adapters/index_elements.py`의 `STRUCTURE_FIRST_VERSION`(구조 우선 전략의 구현 판)과 `KEYWORD_RULES_VERSION`(키워드 규칙 판)이고, 판 요소 함수 `compute_index_elements`가 청킹 해시와 토크나이저 판에 그 둘과 kiwipiepy·kiwipiepy_model의 설치 판(`importlib.metadata`)을 넣는다. kiwipiepy 0.24.1(모델 0.24.0)은 03이 `pyproject.toml`에 이미 들였다.

- [x] TEI 임베딩 어댑터(`Embedder`): 끝점마다 첫 호출 전 `/info` 확인(모델 이름, `max_input_length`가 조각 상한 이상, `auto_truncate`를 로그에), 다르면 "설정 불일치"로 `embedding_unavailable`. `/tokenize`는 `add_special_tokens: false`의 문자열 배열이고, 특수 토큰 수는 켜고 끈 두 번의 차로 센다. `/v1/embeddings`는 `RAG_TEI_BATCH_SIZE`개씩 보내고 `max_client_batch_size`가 더 작으면 그 값으로 낮춘다(명세 "임베딩 서버와 리랭커 어댑터" 절).
- [x] 오류 번역: 400·413·422는 `embedding_rejected`, 424·429·5xx·연결 실패·시간 초과는 `embedding_unavailable`, 벡터 길이가 다르면 `embedding_dimension_mismatch`이고 서드파티 메시지는 옮기지 않는다.
- [x] TEI 스텁(시험이 띄우는 ASGI 앱 하나)이 `/info`, `/v1/embeddings`(결정적 단어 주머니 벡터), `/tokenize`(UTF-8 바이트 오프셋, 특수 토큰), `/rerank`(낱말 겹침 점수)를 흉내 내고 요청 횟수와 마지막 본문을 기억한다(명세 Testing Decisions. 선례 `.scratch/core/probes/embedding/fake_server.py`).
- [x] UTF-8 바이트 오프셋 → 글자 인덱스 변환(누적 합과 이분 탐색, 글자 중간이면 앞 경계)이 한국어·이모지가 섞인 글에서 맞는다.
- [x] Kiwi 키워드 토크나이저: 품사 집합과 웹 형식 토큰, 외국어 소문자, `normalize_coda`, ASCII 문장 부호 떼기, 규칙 판 1(명세 "키워드 토큰" 절. 판의 상수는 03이 둔 자리의 것을 쓴다). kiwipiepy에 py.typed가 없어 우리 스텁을 둔다(ADR 0006). 질의와 조각이 같은 토큰을 낸다.
- [x] `Chunker` 포트 뒤 구조 우선 전략이 규칙 일곱(절 경로 줄은 상한의 4분의 1 안, 넘치는 제목 블록은 문단으로)과 근거 위치(`page`, `section`, `block_kind`, `block_range`)를 지키고, 판에 적힌 전략 이름·상한·겹침을 인자로 받는다. 문장 분리는 kiwipiepy이고 그 판은 03의 판 요소 함수와 같은 값이다. 전략 구현 판도 03이 둔 상수를 쓴다.
- [x] 임베딩·키워드·리랭크에 넣는 글(절 경로 줄, 빈 줄, 조각 글. 절 경로가 비면 조각 글만)을 짓는 함수가 하나 있고, 상한은 그 글의 토큰 수에 특수 토큰 수를 더해 잰다. 07(조각 쓰기)과 09(리랭크의 `texts`)는 이 함수만 쓴다.
- [x] 시험: 청킹 규칙 일곱을 글자 수로 세는 가짜 토큰 세기로(절 경로가 상한의 4분의 1을 넘는 문서, 그보다 긴 제목 블록 포함), 키워드(품사 선택, 전처리), TEI 어댑터(스텁 대상, 배치 크기, `/info` 불일치, 오프셋 변환, 오류 번역).
- [x] 검사 넷이 초록이다. 부품은 `adapters`에 살고 `app`은 포트로만 부른다(import-linter).
