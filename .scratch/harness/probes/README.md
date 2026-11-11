# 하네스 프로브

하네스(`tools/`, `.claude/`, `tests/`의 fixture)를 받치는 측정 스크립트와 그 출력이다. 일지·대기열·티켓·코드 주석이 "쟀다"로 드는 근거는 이 폴더의 파일을 가리키고, 실행 명령은 각 스크립트의 독스트링과 이 표에, 결과 요약은 출력 파일의 끝 문단(읽는 법)에 있다. 표의 모양은 `.scratch/core/probes/README.md`와 같다.

| 프로브 | 무엇을 재는지 | 어디가 근거로 드는지 | 다시 돌 때 필요한 것 | 잰 판 |
|---|---|---|---|---|
| `kiwi_warmup_stall/gil_stall.py` | 다른 스레드가 Kiwi 모델을 처음 적재하는 동안 주 스레드의 `sleep(0.01)` 한 번이 최대 얼마나 걸리는지(GIL). 출력 `gil_stall_out.txt`(적재 3.9~4.8초, 주 스레드 최대 2.6~3.0초 멈춤. 다른 세션의 검사가 돌던 때) | harness 티켓 fixture-preloads-kiwi, `tests/conftest.py` `run_server`의 주석, `tests/server/test_warmup.py`의 회귀 시험, 일지 2026-11-11-0929-core-get-document-text-window.md | 저장소 의존성(kiwipiepy). 저장소 루트에서 `uv run python .scratch/harness/probes/kiwi_warmup_stall/gil_stall.py` | kiwipiepy 0.24.1 |
| `kiwi_warmup_stall/server_first_request.py` | fixture가 돌려준 서버에 보낸 첫 요청의 연결·첫 바이트 시간과 `httpx.Client()` 생성 시간을 세 갈래(기동 뒤 예열 스레드가 적재하는 옛 모양, 예열 no-op, 지금 fixture)로 가른다. 출력 `server_first_request_out.txt`(옛 모양 2.6~4.5초, 나머지 25ms 안, 클라이언트 생성 0.35~0.69초) | 같음. `tests/server/test_authentication.py` 만료 시험의 주석 | 테스트 PostgreSQL(`RAG_TEST_DATABASE_URL`)과 `tests/conftest.py`의 fixture. 저장소 루트에서 그 파일을 `uv run pytest`에 주고 `-p tests.conftest -p no:xdist -q -s`를 붙인다 | kiwipiepy 0.24.1, httpx 0.28.1, uvicorn 0.54.0 |
