# core 04 앱 조립, 토큰 인증, 요청 ID와 로그 일지 · 2026-11-11

티켓 `.scratch/core/issues/04-app-auth-logging.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/04-app-auth-logging`, 작업은 워크트리 `app-auth-logging`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, PR 직전 리뷰, 회고, 다음을 차례로 둔다. PR 봇 리뷰 절은 봇 회차가 끝난 뒤에 더한다.

이 세션은 리뷰 보고를 받은 턴에 일지로 옮기지 않았고(아래 회고의 `review-report-journal-lag`), 컨텍스트가 한 번 압축된 뒤에 일지를 처음 썼다. 그래서 아래 리뷰 절은 PR 본문과 압축 요약, 커밋 메시지, 변이 표에서 다시 모은 것이다. 지적별 원문은 없고 건수와 판정만 있다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세(`.scratch/core/spec.md`)의 인증·관리 API·로그 절, ADR 0001·0005·0014·0015, 직전 일지(`2026-11-11-0042-core-03-migrate-default-records.md`)의 "다음".
- 개발 의존성 `httpx2`를 더했다(`pyproject.toml`, `uv.lock`). MCP SDK의 클라이언트가 `httpx2.AsyncClient`를 받아, 계약 시험이 Authorization 헤더를 실으려면 필요하다.
- 같은 기능의 05(수집 API)는 이 티켓을, 06(TEI·Kiwi·청킹)은 03만 기다린다. 06은 이미 워크트리 `tei-kiwi-chunker`에서 PR #8로 돈다.

## 정한 것

- **미들웨어는 FastAPI 바깥의 순수 ASGI 둘이다.** 안쪽이 인증(`server/auth.py`), 가장 바깥이 요청 문맥(`server/request_context.py`)이다. 인증이 401로 끝낸 요청과 라우트가 없는 경로도 요청 ID와 로그 줄을 남겨야 해서 라우팅보다 앞에 두었다. `BaseHTTPMiddleware`는 스트리밍 응답과 예외 전파를 바꾸므로 쓰지 않았고 `.claude/rules/server.md`에 적었다.
- **인증 판정의 갈래.** 없음·모름·회수는 401 `unauthenticated`, 만료는 401 `token_expired`이고 둘 다 `WWW-Authenticate: Bearer`를 단다. `reader`가 `/mcp` 밖을 부르면 403 `forbidden`이다. `/health`는 인증 없이 통과한다. HTTP가 아닌 연결은 lifespan만 통과시키고 나머지는 1008로 닫는다(기본이 닫힘, 원칙 V).
- **토큰.** 원문은 `rag_` 접두로 만들고 sha256 해시만 저장한다(`app/tokens.py`, `adapters/postgres/token_store.py`). 발급, 목록, 회수는 관리 API(`server/token_api.py`)이고 첫 `admin` 토큰은 `rag-engine bootstrap-token`이 만든다. 살아 있는 `admin` 토큰이 이미 있으면 더 만들지 않는다(`bootstrap_admin_token`).
- **요청 ID는 서버가 만든다.** UUIDv7을 `X-Request-Id` 응답 헤더로 돌려주고, 들어오는 같은 이름의 헤더는 믿지 않아 로그 주입을 막는다.
- **로그에는 경로 템플릿만 남긴다.** FastAPI 0.162는 `include_router`한 라우터를 `app.routes`에 펼치지 않아(`_IncludedRouter`), `create_app`이 토큰 라우터의 `routes`를 따로 합쳐 미들웨어에 넘긴다. 쓰지 않은 대안은 `scope["route"]`를 읽는 것인데, 라우팅 전에 끝나는 401에는 그 값이 없다.
- **허용 호스트는 `값`과 `값:*` 두 꼴로 펼친다.** SDK의 `host:*`는 포트가 붙은 Host만 받아 기본 포트의 `Host: host`가 421이 된다(ADR 0014).
- **서드파티 예외는 타입과 프레임만 로그에 싣는다.** 메시지에 입력 값(질의, 연결 문자열)이 실릴 수 있어서다(원칙 V). 이 저장소가 정의한 예외만 메시지를 싣는다. uvicorn은 `log_config=None`, `access_log=False`로 띄워 자체 접근 로그를 끈다.
- **`serve`가 `load_settings`로 같은 설정을 읽는다.** 설정 오류는 칸 이름만 찍고 종료 코드 1이다(`adapters/settings.py`의 `ConfigurationError`). core 03 일지가 넘긴 `main.py`의 `ValidationError` 직접 처리는 이 티켓에서 `_with_settings` 도우미 하나로 모았다.
- **`request_failed` 이벤트를 더했다.** 안쪽에서 처리하지 못한 예외를 ERROR로 한 줄 남기는 이벤트이고 명세 "로그 이벤트" 목록에는 없다. 개정은 사용자 판단이다(아래 "다음").
- **CI의 `image` 잡**이 `docker run`에 `RAG_DATABASE_URL`, `RAG_DATA_DIR`, `RAG_ALLOWED_HOSTS`를 넘기게 고쳤다. `serve`가 이제 설정을 읽고 시작하기 때문이다.

## 손으로 본 것

- **변이.** 시험이 구현과 함께 자랐으므로 `tools/mutate.py`의 TOML 표(`.scratch/core/probes/auth_logging_mutations.toml`)로 변이 열세 개를 돌렸다. 열세 개 모두 기대한 표지와 함께 빨강이었고 살아남은 변이는 없었다. 열두 개는 첫 커밋에, 열세 번째(응답 시작 뒤 실패의 상태 덮어쓰기)는 둘째 커밋에 더했다.
- **시험이 잡은 실수.** 구현 도중 시험이 직접 잡은 것이 있다. (1) 로그의 경로가 실제 값으로 남았다: `include_router`한 라우터가 `app.routes`에 없어서였고 위 "정한 것"의 합치기로 고쳤다. (2) `Bearer` 뒤가 비었거나 공백뿐인 헤더는 토큰 없음으로 가려야 했다(`_bearer_token`이 값을 `strip()`하고, `test_authentication.py`가 `"Bearer"`와 틀린 토큰, `Basic`, 접두 없는 값을 같은 401로 본다). (3) `_Outcome`이 `status != 0`으로 "응답을 시작함"을 겸해서, 응답 전에 난 예외가 Problem 없이 text/plain 500이 되었다. 둘째 시험은 응답 시작 여부를 상태와 따로 두는 것으로 고쳤다(`_Outcome.response_started`).
- 시험 하네스를 만들며 난 오류는 `make_settings`에 같은 인자를 두 번 넘긴 것, `serve` 시험이 `server` 대신 다른 픽스처를 쓴 것, 표준 오류에 토큰이 안 나온다는 기대를 틀리게 잡은 것이다. 모두 시험을 고쳤다.

## 코드 리뷰

`/code-review`로 두 축을 돌렸다(범위: `origin/main` 이후 작업 트리와 미추적 파일). Critical·Major는 없었고 Minor 15건과 Nit 11건이 나왔다.

고친 것(근거가 코드와 명세에서 확인된 것):
- 토큰 발급 코드의 중복을 `_new_token` 도우미로 모았다.
- 열린 기본값을 가진 자리를 닫는 쪽으로 고쳤다(원칙 V). 일지를 늦게 쓴 탓에 어느 자리인지는 지적 원문으로 확인하지 못했다. 인증 미들웨어는 지금 `/health`와 lifespan 말고는 인증 없이 통과시키지 않고, 비HTTP 연결은 1008로 닫는다.
- 시험이 밟지 않던 경로에 시험을 더했다. 웹소켓 닫기는 `tests/server/test_auth_scope.py`가, 응답 시작 뒤 실패와 시작 전 취소는 PR 직전 리뷰의 Minor와 함께 `tests/server/test_request_context.py`가 밟는다.
- 낡은 독스트링과 README·rules의 문장을 코드에 맞췄다.

남긴 것과 이유(PR 본문 "남긴 위험"에도 있다):
- 닿지 않는 DB에서 `bootstrap-token`이 안내 없이 SQLAlchemy 트레이스백으로 끝난다(연결 타임아웃 약 2분). 명세 "관리 명령"은 설정 오류만 정했다.
- `bootstrap_admin_token`의 확인과 삽입이 한 트랜잭션이 아니라 두 프로세스가 동시에 돌면 둘 다 발급한다. 운영자가 손으로 한 번 치는 명령이라 미뤘다.
- 토큰 목록에 회수 여부 칸이 없다. 명세가 칸을 정하지 않았고 응답 칸을 더하는 것은 계약 판단이다.
- `request_failed`가 명세 "로그 이벤트" 목록에 없다. 명세 개정이 필요해 사용자에게 넘겼다.
- 테스트 도우미의 중복, `token_api` 안의 중복, `scope_state`가 읽으면서 쓰는 점, 라우트 목록 합치기가 손으로 하는 점: 판단 항목이고 지금 동작에 영향이 없다.

다시 돌린 명령: `ruff check .`, `ruff format --check .`, `pyright`(0 오류), `lint-imports`, 검사 러너 전체(`tools/run_checks.py`, 종료 코드 0). 커밋 둘의 pre-commit도 같은 검사를 다시 돌려 초록이었다.

## PR 직전 리뷰

CodeRabbit CLI(`coderabbit-review` 에이전트) 0.7.5가 `Seat: not assigned`인데도 끝까지 돌았다(`review_completed`, 38개 파일). CLI 지적은 0건이었다. 보안 축은 서브에이전트가 diff를 직접 읽어 보충했고 Minor 2, Nit 2가 나왔다.

- 고친 것(Minor, 둘째 커밋 `36b2557`): 스트리밍 도중 예외가 나면 `http_request` 줄이 이미 보낸 200 대신 500을 남겼고, 응답을 시작하기 전에 클라이언트가 끊으면 `status`가 0으로 남았다. 응답을 시작했으면 상태를 덮지 않고, 시작 전 취소는 `null`로 남긴다. ASGI 수준 시험 둘과 열세 번째 변이를 더했다.
- 남긴 것: 쓰레기 베어러 문자열이 요청마다 DB 연결 하나를 쓰고 풀에 `pool_pre_ping`이 없다는 지적은 추측이었고 재현하지 않았다. 어댑터 판단이라 이 티켓에서 건드리지 않았다. 외래 로거(MCP SDK)가 `mcp_stateless=false`에서 세션 ID를 INFO로 남기는 한계는 독스트링에 적었다. 라우트 안에서 나는 500을 밟는 시험이 없다는 것은 인증을 지나 실패하는 라우트가 아직 없어서다.

## 회고

후보 일곱을 냈다. 승인 1, 기각 6, 넘김 0이다. 사용자에게 묻는 것은 없다. 대기열(`uv run python tools/queue_open_rows.py`)은 이 일지로 항목 하나(`review-report-journal-lag`)를 더해 열린 항목 20개가 된다. 만료할 항목은 없었다. 회차 5 이상은 `spec-review-transition-crossing`(8회차)과 `gate-pipe-read-status`(5회차)이고 둘 다 이 세션의 일이 아니다.

승인:
- **리뷰 보고를 받은 턴에 일지로 옮기지 않았다.** 사건: 셀프 리뷰 두 축과 PR 직전 리뷰의 보고를 받고도 이 브랜치의 일지 파일을 만들지 않았고, 컨텍스트가 압축된 뒤에야 일지를 처음 썼다. 판정에 쓸 지적별 원문이 사라져 PR 본문과 압축 요약으로 다시 모았다(이 일지 머리 문단에 그 한계를 적었다). `code-review` 6단계 끝과 `merge.md` 3이 이미 정한 일이라 지침을 어긴 사건이고, 리뷰가 잡은 것이 아니라 일지를 쓰려다 내가 알아챘다. 층: 구현 때 실리는 `implement` 스킬에는 이 단계의 포인터가 없고 `code-review`는 리뷰를 부를 때에야 실린다. 처방은 `implement`의 "Once done, use /code-review" 줄에 한 문장이고 더하는 것이라 다섯 번째에 반영한다. 항목 `review-report-journal-lag` 1회차로 대기열에 두었다. 같은 일을 다룬 열린 항목은 없었다(`--search 일지·옮기·압축·journal·compaction`).

기각:
- **응답 시작 여부를 상태 하나로 겸했다**(`status != 0`). 시험이 구현 도중 그 자리에서 잡았고(응답 전 예외가 text/plain 500이 됨) 고쳤다. 리뷰까지 가지 않았다.
- **FastAPI가 `include_router`한 라우트를 `app.routes`에 펼치지 않는 것을 몰랐다.** 시험이 실제 경로로 잡았고 `.claude/rules/server.md`에 이미 적었다. 이미 반영한 고침이다.
- **편집 직후 IDE의 pyright 진단이 낡은 값으로 떴다.** 02와 03 일지가 이미 기각한 일이고 이번에도 `uv run pyright`가 0 오류로 판정했다. 잘못된 조치가 없었다. 세 번째이지만 손실이 없고, 같은 항목이 대기열에 없어 회차 대상도 아니다.
- **훅이 명령 모양을 거부했다**(파이프와 체인 뒤의 `$?`, 긴 heredoc). 훅이 그 자리에서 막았고 더 단순한 명령이나 Read로 바꿔 이어 갔다. 이미 있는 가드가 일한 것이다.
- **ruff E501(한글 폭 2)** 이 났다. 편집 직후 `ruff format`과 린트가 잡았다.
- **계약 시험이 인증을 모르던 점**(`tests/contract/test_mcp_tools.py`가 Authorization 헤더 없이 접속했다). 이 티켓의 수용 기준이 시험을 고치라고 정했고 그대로 했다. 사건 없이 떠올린 것이다.

## 다음

- core의 프론티어는 05(수집 API)다. Blocked by가 04뿐이고 이 PR이 병합되면 열린다. 06(TEI·Kiwi·청킹)은 PR #8로 이미 돌고, 07은 05와 06을 기다린다. 05는 `server/token_api.py`와 같은 모양으로 라우터를 더하고, 더할 때 `create_app`이 요청 문맥 미들웨어에 넘기는 라우트 목록에 그 라우터의 `routes`도 더한다(`.claude/rules/server.md`). 인증 시험의 `run_server` 픽스처와 `tests/harness.py`를 쓴다.
- 이 브랜치와 PR #8(06)은 `README.md`, `pyproject.toml`, `src/rag_engine/domain/ports.py`, `uv.lock`을 함께 고쳤다. 나중에 병합하는 쪽이 글자 충돌을 푼다. ADR 번호와 헌법 판의 겹침은 없다.
- 사용자가 정할 것(이 PR이 정하지 않았다):
  - `.env.example`을 둘지. 이 티켓은 새 환경 변수를 더하지 않았고 PR 템플릿 체크리스트의 그 줄은 비워 이유를 적었다. 파일을 둘 티켓(05가 수집 설정을 더하면 자연스럽다)을 정하거나 템플릿의 줄을 고칠지 정한다(core 03 일지에서 넘어왔다).
  - 명세 "로그 이벤트" 목록에 `request_failed`를 더할지. 이 PR은 필요한 이벤트라 구현해 두었다.
  - `GET /api/v1/admin/tokens`에 회수 여부 칸을 둘지(수집 API 계약이 아니라 관리 API의 칸이라 계약 판 문제는 아니나 명세가 칸을 정하지 않았다).
  - ADR 0007 본문 8행 포인터와 헌법 patch 1.1.3은 02 일지의 "다음"에서 그대로 열려 있다.
- 열린 일(받을 티켓은 정하지 않았다):
  - `bootstrap-token`이 닿지 않는 DB에서 안내 없이 트레이스백으로 끝나는 것과, 동시에 두 프로세스가 돌면 둘 다 발급하는 것. 설치 방식이 정해질 때 같이 본다.
  - `migrate.upgrade_to_head`의 동시 첫 설치 락(core 03 일지에서 넘어온 것)은 여전히 열려 있다.
  - 쓰레기 베어러 문자열이 요청마다 DB 연결을 쓰는 것과 풀의 `pool_pre_ping`은 어댑터 판단이다. 05가 라우트를 더해 부하가 생기면 재현해 본다.
  - 라우트 안에서 나는 500(`on_unhandled`)을 밟는 시험은 인증을 지나 실패하는 라우트가 생기는 05에서 더한다.
- `review-report-journal-lag`(대기열)는 `implement`의 리뷰 줄에 한 문장을 더하는 것이라 다섯 번째 반복이 되면 chore가 반영한다.
