# fixture-preloads-kiwi: 서버 fixture가 기동 전에 Kiwi를 적재해 첫 요청이 예열에 멈추지 않게 한다

**What to build:** `tests/conftest.py`의 `run_server`가 uvicorn 스레드를 띄우기 전에 시험 스레드에서 `rag_engine.adapters.kiwi.tokenize_keywords("준비")`를 한 번 불러 모델을 적재한다(프로세스마다 한 번 캐시). 앱 lifespan의 예열 스레드가 모델을 적재하는 동안 GIL을 쥐어 기동 직후 서버 루프와 시험 스레드가 함께 수 초 멈췄고, 그 멈춤이 만료 토큰 시험(`tests/server/test_authentication.py`)의 2초 여유를 삼켜 PR #12의 pre-commit에서 두 번 빨갰다. 진단은 일지 `docs/journal/2026-11-11-0929-core-get-document-text-window.md`의 검증 절, 측정은 `.scratch/harness/probes/kiwi_warmup_stall/`. 같은 시험은 만료 시각을 셈하기 전에 `httpx.Client`를 만들어 클라이언트 생성(프로브는 생성 전체를 쟀다. 그 안에 SSL 컨텍스트 생성이 든다는 것은 코드를 읽은 것이다)이 여유 창에 들지 않게 한다. 명세 PR(`docs/get-document-text-window`)에 함께 싣는 harness 티켓이다. 제품 코드는 손대지 않는다.

**대기열:** token-expiry-test-load-margin

**Status:** done

- [x] `run_server()`가 돌아오기 전에 시험 스레드에서 Kiwi 적재가 한 번 돈다(`tests/server/test_warmup.py`의 회귀 시험. 고침 전에 빨갰다)
- [x] 만료 토큰 시험이 클라이언트를 먼저 만들고 그 클라이언트로 발급과 첫 조회를 한다
- [x] 프로브 둘과 출력이 `.scratch/harness/probes/kiwi_warmup_stall/`에 있고 `.scratch/harness/probes/README.md` 표에 행이 있다
- [x] 회고 반영: 대기열 token-expiry-test-load-margin을 닫았다. 처방(여유를 부하와 무관하게, 시계 주입)을 한 것이 아니라 진단이 찾은 사례 둘의 원인(기동 직후 예열 스레드의 Kiwi 적재가 쥐는 GIL)을 fixture의 기동 전 적재로 없애고 시험은 클라이언트를 먼저 만든다. 실시간 2초 창은 남고 그 창이 부하만으로 넘칠 위험은 받아들였다, 일지 2026-11-11-0929-core-get-document-text-window.md
