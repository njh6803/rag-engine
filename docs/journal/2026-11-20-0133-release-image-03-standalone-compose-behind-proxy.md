# release-image 03: 단독 compose가 프록시 뒤에 컨테이너를 띄우고, 시험이 운영자의 차례를 그대로 밟는다 · 2026-11-20

release-image 티켓 여덟 가운데 넷째로 구현한 티켓(`03-standalone-compose-behind-proxy`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/03-standalone-compose-behind-proxy.md`이고 브랜치는 `feature/03-standalone-compose-behind-proxy`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, PR 직전 리뷰, 커밋, 봇 회차, 회고, 다음을 차례로 둔다.

## 준비

- 지시문대로 `tidy-checkouts`를 돌고 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 맞췄다. 나란히 도는 티켓 05(`05-notes-check-guards-upgrade-bang`)와는 서로 독립이다. 05도 `.github/workflows/ci.yml`을 고쳐서 `tools/sibling_overlap.py`가 겹치는 파일로 알렸고, 글자 충돌은 늦게 병합하는 쪽이 푼다.
- 시작할 때 agent-os의 변경을 봤다. `git -C C:/project/agent log --oneline b74a8adf2..origin/dev -- <티켓이 적은 경로>`가 비었다(origin/dev `148c86d08`). 옮길 변경이 없어 사용자에게 묻지 않았다.
- 이 PC의 Docker Compose는 v5.6.1이고 Docker가 쓸 수 있는 메모리는 15.6GiB다. 이 숫자가 리랭커 인자를 정하는 근거가 됐다.

## 한 일

티켓의 확인란 서른세 줄을 모두 채웠다(CI 실행 주소 한 줄만 PR의 CI가 돈 뒤에 채운다).

- `deploy/standalone/compose.yaml`: 서비스는 `proxy`, `postgres`, `embedding`, `migrate`, `server`, `worker`, 프로필 `reranker`의 `reranker`다. 최상위 이름 `rag-engine`, 필수 값 넷(`RAG_ENGINE_NAMESPACE`, `RAG_ENGINE_VERSION`, `RAG_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`)은 비면 멈춘다. 밖으로 열리는 포트는 프록시의 `0.0.0.0:443:8443` 하나다. 띄우는 차례는 PostgreSQL 건강 → 마이그레이션 끝 → 서버와 작업자(작업자는 임베딩 서버도 기다린다) → 프록시(서버가 건강해진 뒤)다. 바깥 이미지 셋(nginx, pgvector, TEI)은 digest로 고정했다.
- `deploy/standalone/proxy/nginx.conf`와 `site.conf`: 주 설정은 `/etc/rag-engine/proxy/nginx.conf`이고 compose가 `-c`로 준다(04가 설치 안내에 옮길 경로). 넘기는 경로는 `= /mcp`, `/api/v1/ingest/`, `/api/v1/admin/`, `= /health` 넷이고 나머지는 404다. TLS 1.2와 1.3, HSTS, 질의 문자열이 없는 접근 로그, 사이트의 `error_log /dev/null`, 뒷단 이름을 5초마다 다시 푸는 설정을 실었다.
- `deploy/standalone/.env.example`: 표지 둘, 빈 필수 값 둘, 주석 처리한 예시 둘.
- `tests/standalone/test_standalone_compose.py`(새 파일): 운영자가 하는 차례(묶음 풀기, `.env` 채우기, 인증서, 모델 폴더, `up -d --wait --wait-timeout 1800`)를 그대로 밟고 공식 MCP SDK 클라이언트로 443에 접속해 검색하는 시험 24개다. `pyproject.toml`의 `norecursedirs`로 기본 수집에서 빼고 경로를 주어 칠 때만 모은다.
- `.github/workflows/ci.yml`: `standalone` 잡. 늘 시작하고 체크아웃 다음 스텝(gate)이 base가 main인 PR과 main 푸시에서만 시험하게 정한다. `verify.needs`에 이름만 더했고 머리 주석의 잡 개수를 여섯으로 고쳤다.

## 확인한 것

- 빨강을 먼저 봤다. `deploy/standalone/`이 없을 때 시험은 마당(fixture)에서 오류로 끝났다. 배포 파일을 쓴 뒤 24개가 초록이 됐다.
- 개발 PC에서 끝까지 돌린 결과는 `24 passed in 161.64s`였고, 리랭커 인자를 고친 뒤 `223.37s`, 셀프 리뷰를 반영한 뒤 `350.00s`였다. 건너뛴 시험은 없다. 모델은 Docker 볼륨 `rag-latency-probe_tei-data`에서 `models--BAAI--bge-m3`만 링크를 풀어 복사한 폴더를 썼다.
- 일부러 깨뜨린 사본으로 시험이 빨개지는 것을 셋 봤다. `/docs`를 넘기게 한 설정과 접근 로그의 `$request_uri`(4개 빨강), `error_log /dev/null`을 뺀 설정(서버를 멈춘 채 보내는 요청 시험이 빨강), `ssl_protocols`에 1.1을 넣은 설정(셀프 리뷰 뒤에 더한 단언이 빨강). 깨뜨린 사본은 모두 되돌렸고 커밋하지 않았다.
- 손으로 본 것: 실제 서버의 `/mcp` 응답이 프록시를 지나도 `text/event-stream`, `transfer-encoding: chunked`이고 `X-Accel-Buffering`은 없다. 리랭커는 `--max-batch-tokens 4096`일 때 5.838GiB(같이 뜬 임베딩 서버는 5.169GiB)이고, 인자 없이 띄운 시도는 두 번 다 끝나지 않았으며 까닭은 가리지 못했다.
- nginx 문서(`ngx_core_module.html#error_log`)를 `curl`로 받아 본문을 읽었다. 문맥 사이로 물려주는 규칙은 거기 없어, `error_log /dev/null`이 요청 줄의 유출을 막는지는 깨뜨린 사본의 시험으로 갈음했다.
- 최소 판 Compose 2.20.2에서는 재지 못했다. 실행 파일을 내려받는 일은 사용자의 허락이 있어야 해서 받지 않았고, 04에 "최소 판에서는 재지 않았다"를 그대로 두게 넘겼다.
- 회복 시간 15초 단언은 서버를 죽이는 시험만 홀로 돌린 이 PC에서 8.0초와 9.5초였고, 깨뜨린 사본으로 전체를 느리게 돌린 실행에서 19.2초가 나와 빨개진 적이 있다. 명세의 수치라 시험에서 늘리지 않았다.

## 셀프 리뷰

`/code-review`를 기준 `fa85261`(파일 8개, 커밋 0개, 미추적 0개)으로 돌렸다. 표준 축에서 Major 셋과 Minor 다섯, 명세 축에서 Major 없이 Minor 여럿이 나왔다. 지적마다 코드와 문서에 대 보고 판정했다.

- 고친 것: ① 리눅스에서 TLS 대조 서버가 스택의 키(`root:101`, `0640`)를 읽다 `PermissionError`가 나는 길을, 대조 서버가 자기 인증서를 새로 만들게 해 없앴다(이 PC는 Windows라 그 소유 변경이 건너뛰어져 안 보였다). ② `asyncio.run()` 직접 호출 둘을 `async def` 시험으로 바꿨다. ③ 없음을 `-1.0`·`0`으로 나타내던 곳을 `None`으로 바꿨다. ④ `compose.yaml`의 머리 주석과 리랭커 주석을 사실에 맞췄다. ⑤ 티켓 Comments의 `쟀다`와 `12GiB 안팎`을 손으로 본 값과 `11GiB 안팎`으로 고쳤다. ⑥ 시험 독스트링의 `finally` 서술과 `MODEL_FOLDER_COMMANDS` 설명을 고쳤다. ⑦ PostgreSQL과 임베딩 서버 로그가 비어 있지 않다는 단언을 더했다. ⑧ TLS 1.1 단언이 nginx 설정과 무관하게 초록이던 것을, 실행 중인 프록시에서 `nginx -T -c`로 `ssl_protocols` 줄을 읽어 맞대는 단언으로 보강했다(깨뜨린 사본에서 이 단언이 빨개졌다).
- 남긴 것과 이유: 회복 시간 15초가 `tests.md`의 "홀로 돌린 시간의 넉넉한 배수" 규칙과 어긋나는 것은 명세가 정한 수치라 그대로 두고, 까닭과 관찰한 시간을 `RECOVERY_SECONDS` 옆 주석과 티켓 Comments에 적었다. 냄새로 나온 `docker compose -p` 중복과 `(directory, namespace, version)` 묶음은 판단 항목이고 시험 파일 하나 안의 일이라 고치지 않았다.
- 다시 돌린 것: 저장소 전체의 `ruff check`, `ruff format --check`, `pyright tests/standalone`이 통과했다. 전체 검사는 아래 "커밋"의 pre-commit이 갈음했다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 CodeRabbit CLI로 로컬 변경(기준 `origin/dev`)을 보안·버그·성능 축으로 봤다. 지적마다 코드와 명세에 대 보고 판정했다.

- 고친 것: ① `stack` 마당의 `finally`가 `save_logs`를 먼저 부르고, 그 호출이 예외를 내면 `down -v`, 도우미 컨테이너 제거, 소유 되돌리기가 모두 건너뛰어졌다. 남은 컨테이너와 볼륨은 다음 실행의 443을 막는다. 로그 저장을 안쪽 `try`로 감싸 뒤의 정리가 늘 돌게 했다. ② `until_ready`의 독스트링이 제한 안에 200이 없으면 `None`이라고만 적었는데, 제한은 다음 물음을 시작할지만 정하므로 마지막 물음이 제한을 넘겨 200을 받으면 제한보다 큰 값이 돌아온다. 그 사실을 적었고 호출하는 쪽(`seconds is not None and seconds <= RECOVERY_SECONDS`)이 이미 다시 견준다. ③ `RECOVERY_SECONDS` 옆 주석이 19.2초를 다른 일이 겹친 실행이라고 적었는데, 그 값은 깨뜨린 사본으로 전체를 느리게 돌린 실행에서 나왔다. 8.0초와 9.5초는 서버를 죽이는 시험만 홀로 돌린 값이다. 둘을 가르도록 고쳤다. ④ `ci.yml`의 `standalone` 잡 주석이 gate를 첫 스텝이라고 적었는데 첫 스텝은 체크아웃이다. 체크아웃 다음 스텝으로 고쳤다. 일지 본문의 같은 문구 둘도 함께 고쳤다.
- 판정해 남긴 것: 재생성 시각부터 회복 시간을 재야 한다는 지적은 명세가 건강해진 뒤부터 15초를 재라고 적은 것과 같아서 그대로 둔다. 기본 인자로 띄운 리랭커가 끝나지 않은 까닭을 모른다는 지적은 이미 티켓 Comments에 손으로 본 값과 모름으로 적었다.
- 다시 돌린 것: `ruff check`, `ruff format --check .`, `pyright tests/standalone`이 통과했다. 시험 24개는 다시 돌리지 않았다. 고친 곳은 정리 순서의 감싸기, 독스트링, 주석, 워크플로 주석이라 시험의 판정을 바꾸지 않는다. 전체 검사는 아래 커밋의 pre-commit이 갈음한다.

## 커밋

- `912d3e2` 기능 커밋: pre-commit의 `ruff check`, `ruff format`, 병렬 검사(`test-db`, `check-ticket`, `lint-imports`, `zizmor`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest` 466.5초), 표 검사, 줄 구분자 검사, 변이 표 검사, 따옴표 인용 대조(경고만), 커밋 메시지 검사가 모두 통과했다.
- `78c21e6` 티켓 Comments의 따옴표 인용을 풀어쓴 문서 커밋. 인용 대조 경고 다섯이 모두 내가 쓴 문구에 붙인 따옴표여서 원문이 있는 인용이 아니었고, 따옴표를 뗐다.
- 합치기: `origin/dev`(`ed395e7`, 리뷰 봇 지시문의 판)를 이 브랜치에 합쳤다. 충돌은 없었고 `tests/test_plan_status.py`는 13개가 통과했다.

## 봇 회차

(PR을 연 뒤 채운다.)

## 회고

(PR을 연 뒤 `retro`로 채운다.)

## 다음

(PR을 연 뒤 채운다.)
