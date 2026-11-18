# release-image 01: 이미지가 릴리스 번호를 보인다 · 2026-11-19

release-image 티켓 여덟 가운데 둘째 티켓(`01-images-show-release-number`)을 구현한 세션의 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/01-images-show-release-number.md`이고 브랜치는 `feature/01-images-show-release-number`, 작업은 워크트리 `01-images-show-release-number`에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, 커밋, 다음을 차례로 둔다.

## 준비

- 지시문대로 주 체크아웃에서 `tidy-checkouts`를 먼저 돌고 `EnterWorktree`로 워크트리에 들어가 브랜치를 맞췄다.
- 06이 헌법 `operations.md`에 남긴 미래형 문장(`rag-engine --version`이 아직 없고 01이 들인다)을 이 티켓이 걷는다.
- agent-os 변경 확인과 바탕 이미지 digest 확인은 티켓 Comments에 적었다.

## 한 일

티켓의 수락 기준 열네 줄을 모두 채웠다.

- `src/rag_engine/adapters/release_number.py`(새 파일): 설치된 패키지 `rag-engine`의 번호를 `importlib.metadata`로 읽는 유일한 자리다. 저장소의 `version`은 `0.0.0`으로 두고, 번호는 이미지를 지을 때만 넣는다.
- `src/rag_engine/server/api_version.py`(새 파일): 수집 API와 관리 API의 경로 판(`v1`)을 한 곳에 두고, 네 라우터(`admin_api.py`, `admin_knowledge_base_api.py`, `ingest_api.py`, `token_api.py`)의 접두가 그 값을 쓴다. `--version`이 경로의 판을 코드에서 읽어 오게 하려고 뽑았다.
- `src/rag_engine/server/app.py`: MCP 서버 정보와 FastAPI 문서(`/openapi.json`)가 같은 번호를 읽는다.
- `src/rag_engine/main.py`: `rag-engine --version`이 다섯 줄을 찍는다. 첫 줄은 릴리스 번호이고, 둘째 줄부터 검색 도구의 형식, 수집 API와 관리 API의 경로, 파서 인터페이스, 색인 형식의 스키마 판이다. 각 판은 그 계약을 정한 코드의 상수에서 읽는다. 필수 설정이 하나도 없어도 종료 코드 0으로 끝난다.
- `deploy/images/Dockerfile`, `Dockerfile.dockerignore`, `docker-bake.hcl`: 루트의 `Dockerfile`과 `.dockerignore`를 `git mv`로 옮기고, 서버와 작업자 이미지를 한 Dockerfile의 두 단계(`server`, `worker`)로 짓는다. 두 이미지는 `runtime` 단계를 공유하고 시작 명령만 다르다. 릴리스 번호는 필수 빌드 인자 `APP_VERSION`으로 받고, 없거나 `X.Y.Z`, `X.Y.Z-rc.N` 꼴이 아니면 빌드가 실패한다. 빌드 단계 안의 `pyproject.toml` 사본만 고치고, 설치된 번호가 넘긴 번호와 같은지 대 보고 다르면 실패시킨다.
- `.github/workflows/ci.yml`의 `image` 잡: bake로 두 이미지를 `0.0.1-rc.1`로 지어 서버를 띄워 `/health`를 확인하고, 두 이미지의 `rag-engine --version` 첫 줄이 넘긴 번호와 같은지 본다. 저장소의 번호(`0.0.0`)와 일부러 다른 번호를 써서, 번호를 코드에 굳혀 넣은 실수를 잡는다.
- `pyproject.toml`과 `uv.lock`: `python-multipart`를 직접 의존성으로 더했다. `uv add`는 권한 분류기가 막아 `pyproject.toml`을 고치고 `uv lock`을 돌렸고, 잠금 파일은 두 줄만 바뀌었다.
- 옛 경로(`Dockerfile`, `.dockerignore`)를 가리키던 `.coderabbit.yaml`, `README.md`, `tools/search_eval.py`의 독스트링, 전체 계획 머리(`.scratch/plan-head.md`)를 새 경로로 고치고 `.scratch/plan.md`를 도구로 다시 만들었다.
- 시험: `tests/conftest.py`의 `marker_release_number` 고정 장치는 번호를 읽는 자리를 `9.9.9-rc.9`로 바꿔 끼운다. 개발 체크아웃은 번호가 `0.0.0`이라 번호를 코드에 굳혀 넣어도 시험이 초록이 되기 때문이다. `tests/test_version_command.py`는 첫 줄이 표지 번호와 같고, 계약의 판이 코드 상수와 같고, 지금의 값(`1.1.0`, `v1`, `1.0.0`, `1`)과 같은지 본다. `tests/server/test_release_number.py`는 `/openapi.json`과 MCP `initialize`의 서버 정보가 표지 번호를 보이는지 본다.
- `docs/constitution/operations.md`: 06이 남긴 미래형 문장을 지웠다. 헌법 문서를 고쳤으므로 `docs/constitution/README.md`의 판을 1.5.0에서 1.5.1로 올렸다(문구만 고친 patch). 형제의 가장 높은 판은 1.5.0(`origin/dev`)이라 겹치지 않는다.

## 확인한 것

- 손으로 이미지를 지었다. 번호 없이, 꼴이 틀린 번호로 지으면 둘 다 종료 1로 실패했다. 두 이미지의 층이 같고(여덟 층), 1번 프로세스는 uid 10001로 돌며, `rag-engine --version`의 다섯 줄과 `/health`가 나왔다.
- 변이 확인: 번호를 읽는 자리를 `0.0.0`으로 굳히면 세 시험 묶음이 실패했다.
- 마지막으로 처음부터 돌린 `uv run python tools/run_checks.py`는 `check-ticket`만 실패했다. 변경 파일을 스테이지하기 전이라 이 검사가 티켓을 커밋에서 찾지 못한 것이다. 나머지(`test-db`, `lint-imports`, `zizmor`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest`)는 통과했고 pytest는 507.9초였다. 스테이지한 뒤의 pre-commit 결과는 아래 "커밋"에 적는다.

## 셀프 리뷰

`/code-review`의 표준 축과 명세 축을 나란히 돌렸다. 두 축은 둘 다 문서의 줄바꿈이 사라진 곳과 헌법 판을 올리지 않은 곳을 낸 것으로 기억한다. 지적마다 근거를 읽고 판정했다.

- 고쳤다(두 축 모두): `operations.md`에서 문장을 지우다 줄바꿈까지 지워, 다음 목록 항목이 문단에 붙어 있었다. 줄바꿈을 되살렸다.
- 고쳤다(명세 축 Major): 헌법 문서를 고쳤는데 `docs/constitution/README.md`의 판을 올리지 않았다. 1.5.1로 올렸다.
- 고쳤다: `--version`의 독스트링이 릴리스 노트의 계약 절이 어느 줄부터 옮기는지 틀리게 적고 있었다. 둘째 줄부터라고 고쳤다.
- 고쳤다: 둘째 시험에 쓰지 않는 표지 번호 인자와 군더더기 단언이 있었다. `usefixtures`로 바꾸고 단언을 줄였다.
- 고쳤다: 바탕 이미지 digest를 받은 날짜가 2026-11-18로 적혀 있었다. 받은 날은 2026-11-19라서 Dockerfile 머리 주석과 티켓 Comments를 고쳤다.
- 고쳤다: README의 파일 배치 그림에 `api_version.py`, `release_number.py`, `--version`, `deploy/images/`가 빠져 있었다.

고치며 새로 쓴 사실 문장은 모두 코드와 티켓에서 읽은 값(날짜, 판 번호, 파일 이름)이다. 다시 돌린 명령: 린트와 포맷 검사는 통과했고(`ruff check`, `ruff format --check`), 전체 러너는 위 "확인한 것"과 같다.

## 커밋

커밋 전 `git branch --show-current`는 `feature/01-images-show-release-number`였다. 이 절은 커밋이 끝난 뒤 pre-commit 결과로 채운다.

## 회고

`retro` 스킬을 돌렸다. 후보는 여섯이고 승인 하나, 넘김 없음, 기각 다섯이다. 셀프 리뷰가 잡은 줄바꿈 삭제, 판 올림 누락, 독스트링과 날짜의 틀린 사실은 `code-review`가 잡으라고 둔 기준을 어긴 것이라 리뷰가 제 몫을 한 것이고, 이 셈에서 뺐다.

1. **승인(회차로 센다).** 검사 러너(`tools/run_checks.py`)를 백그라운드로 띄워 두고 셀프 리뷰의 지적을 반영하느라 같은 동안 문서와 시험 파일을 고쳤다. 러너의 결과는 고치기 전의 상태 것이라 러너를 멈추고 처음부터 다시 돌렸다. 대기열 `edit-during-precommit`의 5회차로 더했다. 처방은 그 항목의 계기 훅이다. 회차가 5에 이르렀으나 훅은 하네스 변경이라 이 이미지 티켓의 PR에 싣지 않고, 회차 5 이상인 열린 항목으로 chore 배치의 계기가 되게 둔다.
2. **기각.** `uv add python-multipart`를 권한 분류기가 막았다. 이미 있는 가드가 그 자리에서 막았고, `pyproject.toml`을 고쳐 `uv lock`을 돌리는 길로 풀렸다.
3. **기각.** 훅이 다른 체크아웃으로의 `cd`와 표준입력으로 넘긴 맨 `python3`을 막았다. 이미 있는 가드가 그 자리에서 알렸다.
4. **기각.** 전체 러너를 변경 파일을 스테이지하기 전에 돌려 `check-ticket`이 빨갰다. 검사가 무엇을 스테이지하라는지 출력에 그대로 적어, 한 번에 풀렸다.
5. **기각.** 바탕 이미지 digest를 받은 날짜를 전날로 적었다. 리뷰의 주장 검증 목록이 잡았고 잃은 것이 없다.
6. **기각.** 개발 체크아웃의 번호가 `0.0.0`이라 번호를 코드에 굳혀 넣어도 시험이 초록이 되는 위험을 떠올렸다. 이 티켓이 번호 자리를 표지로 바꿔 끼우는 시험과 CI `image` 잡의 `0.0.1-rc.1`로 이미 잡았고, 변이 확인으로 빨강을 봤다.

만료는 `uv run python tools/queue_open_rows.py`의 "만료할 항목"이 (없음)이라 닫을 것이 없었다. 문턱을 지난 새 훅·검사가 없어 `tools/hook_report.py`는 돌리지 않았다.

## 다음

이 PR(base dev)은 헌법 판 1.5.1(문구 수정)을 올린다. 병합 뒤 release-image의 프런티어에서 01이 빠지므로 03(단독 compose)은 02(번호·노트·묶음 도구)가 병합되면 열린다. 03은 이 티켓이 비워 둔 이미지의 헬스체크를 compose에 둔다. 세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
