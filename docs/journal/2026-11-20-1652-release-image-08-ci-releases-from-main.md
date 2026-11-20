# release-image 08: main이 움직이면 CI가 번호를 계산해 이미지 둘과 GitHub 릴리스를 낸다 · 2026-11-20

release-image 티켓 여덟 가운데 마지막으로 구현한 티켓(`08-ci-releases-from-main`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/08-ci-releases-from-main.md`이고 브랜치는 `feature/08-ci-releases-from-main`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 사람 몫, 셀프 리뷰를 차례로 두고, PR 직전 리뷰와 검사와 커밋은 그 뒤에, 봇 회차와 회고와 다음은 PR을 연 뒤에 잇는다.

## 준비

- 새 세션이라 `tidy-checkouts`를 먼저 돌았다. 루트를 `8e7e930`에서 `cdf3bc5`로 당겼고, 병합된 워크트리 셋(01, 03, `glossary-ask-remaining-names`)과 그 브랜치, `worktree-04-install-guide-walks-operator`를 지웠다. 실행 중 세션이 쥔 것, 바뀐 파일이 있는 것, 앱 표지가 있는 것, 14번 워크트리는 남기거나 사람에게 넘겼다. 휴지통 `.venv`는 `WinError 5`로 남았다.
- 시작할 때 agent-os의 변경을 봤다. 두 명령이 모두 종료 0이고 출력이 비어 옮길 변경이 없었다. 사용자에게 묻지 않았다.
- 이어받은 상태 둘: 04 PR의 Minor 보류(`test_deploy_guide.py`의 폐쇄망 시험이 로컬 이름을 글자 그대로 박은 것. 바깥 이미지의 digest를 바꾸는 변경이 올 때 고친다. 08은 바깥 이미지를 바꾸지 않아 08의 일이 아니다), 원격 브랜치 `feature/04-install-guide-walks-operator`가 지워지지 않은 것(권한 분류기가 `git push origin --delete`를 거부했고 우회하지 않았다. 사람이 지우거나 지워도 된다고 허락한 세션이 지운다).

## 한 일

- `.github/workflows/release.yml`(새 파일): main 푸시에서만 도는 잡 둘(`build`, `publish`)이다. `build`는 번호와 노트 계산, 이미지 둘 짓기(시험용), 배포 파일 묶음 짓기, 단독 compose 시험, 점검(Grype, Syft), 노트 짓기, Docker Hub 로그인, 커밋 태그로 올리기, 시험한 이미지와 올린 이미지 대조, 아티팩트 올리기 순이다. `publish`는 아티팩트 대조, 사전 확인, 초안, 자산, 번호 태그, 공개, 정리 순이다.
- `tools/release_ci.py`(새 파일): 워크플로가 단계 사이에서 부르는 판정 도구다. agent-os의 것을 이미지 둘과 `rag-engine-` 이름으로 옮겼다.
- `deploy/release.toml`(새 파일): `candidate_for = "0.1.0"` 한 칸이다.
- `tests/tools/test_release_ci.py`, `tests/tools/test_release_workflow.py`(새 파일): 도구 시험과 워크플로 꼴 시험이다. 저장소 상태 시험으로 `Dockerfile`과 compose의 바깥 이미지 digest 고정, compose의 서비스와 우리 이미지 짝, 프록시 `/mcp`의 `proxy_buffering off`를 더했다.
- `docs/release-notes/features/release-image.md`(241자 한 단락), `docs/release-notes/intro/0.1.0.md`(core와 search-eval을 설명하는 소개 글).
- 문서 맞춤: `operations.md`의 단계 이름과 낡은 문장, `tech.md`의 "값은 그때 확정한다" 두 곳, `ci.yml` `image` 잡 머리 주석, 헌법 버전 1.5.4에서 1.5.5(문구 수정, patch), 기능 계획의 `**끝:** 2026-11-20`과 전체 계획 표.

## 확인한 것

- 액션 8개의 해시가 주석의 태그를 가리키는지 `gh api`로 대 보았다.
- `uv run zizmor --offline --strict-collection --config .github/zizmor.yml .`: `No findings to report`.
- 저장소 상태 시험 셋과 워크플로 시험 다섯을 진짜 파일에서 일부러 깨뜨려 빨개지는 것을 손으로 봤고, 원래대로 되돌렸다.
- 단독 compose 시험을 이 PC에서 모델 폴더 없이 한 번 더 돌렸다. `25 passed in 583.61s (0:09:43)`(임베딩 서버의 첫 시작이 모델을 내려받았다).
- 못 잰 것: 워크플로 자체의 실행(GitHub 러너에서 돈 적이 없다), 리눅스에서의 단독 compose 시험, main 푸시에서 모델 캐시를 읽을 수 있는지.

## 사람 몫

사용자에게 한 화면으로 보인 목록이다. 비밀 값은 사용자가 직접 넣고 세션에 넘기지 않는다.

1. Docker Hub: 계정 `njh6803`에 공개 저장소 둘 `rag-engine-server`, `rag-engine-worker`를 만들고, 이 둘에 읽기·쓰기를 주는 접근 토큰 하나를 만든다.
2. GitHub 환경 `release`: 저장소 설정의 Environments에서 `release`를 만들고, 배포 브랜치를 `main` 하나로 좁힌다.
3. 환경 `release`의 비밀 값 둘: `DOCKERHUB_TOKEN`(1의 접근 토큰), `RELEASE_GH_TOKEN`(저장소 `njh6803/rag-engine` 하나에 Contents와 Workflows의 읽기·쓰기만 준 세분 토큰).
4. 환경 `release`의 변수 하나: `DOCKERHUB_NAMESPACE` = `njh6803`.
5. squash 병합의 제목을 PR 제목으로 쓰는 저장소 설정(지금 값은 `COMMIT_OR_PR_TITLE`).

`RELEASE_GH_TOKEN`의 만들기 주소는 GitHub 문서가 적은 템플릿 꼴이다. 이름, 설명, 소유자, 만료 일수, 권한을 미리 채우고, 저장소 하나로 좁히는 일은 화면에서 직접 한다. 권한 이름 `workflows`는 이 세션에서 열어 보지 않아, 화면에서 비어 있으면 직접 고른다.

`https://github.com/settings/personal-access-tokens/new?name=rag-engine-release&description=rag-engine+release+workflow&target_name=njh6803&expires_in=90&contents=write&workflows=write`

## 셀프 리뷰

`/code-review`를 기준 `origin/dev`로 돌렸다. 범위는 기준 `cdf3bc5`, 고친 파일 일곱 개, 새 파일 여덟 개(원고 폴더 하나에 둘), 커밋 없음이다. 표준 축은 Minor 다섯과 Nit 몇 개, 명세 축은 Major 하나(소개 글의 닫힌 주장)와 Minor 몇 개를 냈다.

- 고친 것: ① `intro/0.1.0.md`의 "설치한 서버에는 들어 있지 않고"는 이미지가 `COPY src`로 평가 모듈을 싣기 때문에 닫힌 주장이 틀렸다. "평가를 돌리는 명령은 들어 있지 않고"로 좁혔다(Major). ② 같은 글의 "마이그레이션은 처음 띄울 때 한 번"을 "띄울 때마다 서버보다 먼저"로 고쳤다. ③ compose의 서비스와 우리 이미지 짝을 시험으로 더했다(맞바꾼 사본을 잡는 변이 짝 포함). ④ 단계 차례(시험과 점검 앞 로그인, 로그인 뒤 올리기, 올리기 뒤 대조, 점검 뒤 노트)를 `STEP_ORDER` 도우미와 변이 시험으로 고정했다. ⑤ `operations.md` 44행의 "순서가 중요한 이름 다섯"을 시험이 실제로 보는 것으로 낮췄다. ⑥ 낡은 미래형 둘("07이 더한다", "08이 들인다")을 지난 일로 고쳤다. ⑦ `release_ci.py`의 overlay2 문장이 agent-os가 잰 것임을 밝혔다. ⑧ 머리 주석의 "밀려난 실행의 변경도 그 릴리스에 실린다"에 조건을 달았다. ⑨ `setup-uv`의 캐시를 끈 까닭을 주석에 적었다.
- 남긴 것: ① 취소나 제한 시간으로 `publish`가 초안을 남기면 이어지는 푸시의 `build`가 지은 뒤에야 막히는 낭비(agent-os와 같은 구조), ② 단계 이름의 옛 낱말 `판`, ③ main 푸시에서 모델 캐시를 읽는지. 모두 티켓 Comments에 적었다.
- 다시 돌린 것: `ruff check`, `pyright`, `tests/tools/test_release_ci.py`, `test_release_workflow.py`, `test_release.py`(`196 passed`). 전체 검사는 커밋의 pre-commit이 갈음한다.
- 반영으로 새로 쓴 사실 문장(PR 직전 리뷰에 밀 주장으로 넘겼다): 소개 글의 평가 명령이 설치한 서버에 들어 있지 않다는 문장과 마이그레이션이 서버를 띄울 때마다 서버보다 먼저 돈다는 문장(뒤의 것은 PR 직전 리뷰에서 고쳤다), `release.yml`의 `uv 준비` 위 주석(캐시를 끄는 까닭)과 머리 주석의 조건 문장, `STEP_ORDER`와 `own_repository_by_service` 독스트링의 "못 보는 것", `release_ci.py` 독스트링의 agent-os가 잰 것이라는 문장, `operations.md` 41·44행의 고친 문장.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트가 CodeRabbit CLI(0.7.5, `--include-untracked`)로 돌았다. 새 파일 일곱이 모두 `reviewedFiles`에 들었고 지적은 열 건이다. 서브에이전트는 첫 실행에서 40턴 한도에 걸려 보고 없이 멈췄고, 한 번 이어 달라고 해서 보고를 받았다. Critical과 Major는 없다. 서브에이전트가 직접 재 본 것은 이 PC의 `docker save` 꼴, `image-id` 출력, 액션 해시 일곱, `zizmor`(지적 없음), 도구 함수 호출이다. 못 잰 것은 러너에서의 실행, 레지스트리에 올린 이미지와 로컬 이미지의 설정 해시 비교, 재실행 때의 concurrency 동작이다.

- 고친 것(전부 Minor): ① `release_ci.py` 독스트링과 `test_release_ci.py` 머리의 저장 방식 분류가 틀렸다. 이 PC(Docker 29.9.2, overlay2)의 `docker save`가 `blobs/sha256/<해시>` 꼴을 내고 그 값이 `docker image inspect`의 `Id`와 같았다. 엔진 판에 따라 두 꼴이 갈린다고 고치고 이 PC에서 읽은 값을 적었다. ② `release.yml` 137행 주석이 다른 실행이 만든 캐시를 읽지 않는다고 썼으나 같은 잡이 모델 캐시를 복원한다. uv 캐시 이야기로 좁히고 모델 캐시는 읽기만 하며 이미지에 들어가지 않는다고 적었다. ③ `release.yml` 머리의 동시 실행 문장이 "더 나중 실행"이라 썼으나 실패한 옛 실행을 다시 돌리면 옛 커밋이 새 커밋의 대기 실행을 밀어낼 수 있다. 커밋 기준으로 고치고 코드로 읽었을 뿐 재 보지 않았다고 적었다. ④ `정리` 단계가 태그 조회 실패를 "태그 없음"으로 읽었다. 조회 실패는 경고로 드러내고 마지막 줄에 `deleted`·`gone`·`unknown`으로 태그 상태를 찍는다. ⑤ `unpinned_compose_images`가 `image:` 값 뒤의 주석에 적은 digest로 통과했다. 주석을 떼고 보게 하고 주석 digest 입력과 주석이 붙은 고정 입력을 시험에 더했다. ⑥ `unpinned_from`이 파일 전체의 `ARG`를 모았다. 첫 `FROM` 앞의 것만 읽게 고치고(Docker 규칙) 두 입력을 시험에 더했다. ⑦ `own_repository_by_service`와 `out_of_order`의 "못 보는 것"에 서브에이전트가 호출로 찾은 입력(서비스 머리 뒤 주석, 따옴표 친 값, 변수 저장소 이름, 따옴표·주석이 붙은 단계 이름, `- id:` 단계)을 적었다. ⑧ `operations.md` 44행의 이름 "다섯"이 `STEP_ORDER` 기준 여섯이었다. `이미지 올리기`를 더해 여섯으로 고쳤다. ⑨ `intro/0.1.0.md`의 마이그레이션 문장을 "설치 안내대로 `docker compose up`으로 띄울 때마다"로 좁혔다. 도커 데몬이 재시작해 서버만 다시 뜰 때는 마이그레이션이 다시 돌지 않는다.
- 남긴 것: 서버 이미지 디스크 여유(CLI 1번, 이 PC의 이미지가 각 524MB라 표준 러너를 넘긴다는 근거가 없고 러너에서 재지 못했다), 취소로 남은 초안을 지우는 설계(CLI 5번, `release.yml`과 `operations.md`가 이미 문서로 정한 결정), 모델 캐시 파일 모드(CLI 6번, `ci.yml`의 standalone 잡이 같은 복사를 한다, 재현하지 못했다), 로그 업로드(CLI 7번, `ci.yml`과 같은 패턴이고 로그는 시험용 값뿐이다). 이동한 마이그레이션 검사(CLI 2번)는 이 변경이 `check_notes`를 건드리지 않아 범위 밖이고, 태그가 조상이 아닐 때(CLI 3번)는 `tools/release.py`의 `_ensure_ancestor`가 빨갛게 끝낸다.
- 오탐으로 가른 반례: 소개 글의 "평가를 돌리는 명령은 …들어 있지 않고"는 이미지의 `rag-engine --help`가 다섯 하위 명령(`serve, migrate, worker, bootstrap-token, ingest`)뿐이라 맞았다. 리랭커 기본 꺼짐, 최소 점수, MCP 토큰, 읽기 도구 셋도 코드로 맞았다. `operations.md` 41·44·47·63행의 단계 이름은 `release.yml`과 모두 일치했다.
- 다시 돌린 것: `ruff check`, `ruff format --check`, `pyright`(오류 0), `test_release_ci.py`·`test_release_workflow.py`·`test_release.py`(`196 passed`), `zizmor`(지적 없음). 전체 검사는 커밋의 pre-commit이 갈음한다.
## 검사와 커밋

- 커밋 `42a13b5`(브랜치 `feature/08-ci-releases-from-main`)의 pre-commit이 `ruff check`, `ruff format`, 검사 러너(`test-db`, `zizmor`, `check-notes`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright-linux`, `pyright`, `run-hooks`, `pytest` 452.7초), 표·줄 구분자·변이 표·헌법 버전·커밋 메시지 훅을 모두 통과했다. `tools/sibling_overlap.py`는 번호 겹침 없음(헌법 1.5.5, 형제 최고 1.5.4)이다.
- 인용 대조가 경고 둘을 냈다. 둘 다 PR 직전 리뷰에서 고치기 전의 옛 문장을 따옴표로 옮긴 것이라 따옴표를 떼는 후속 커밋으로 고쳤다.

## 반영으로 새로 쓴 문장

- 반영으로 새로 쓴 사실 문장(봇 회차에 밀 주장): `release_ci.py` "못 보는 것" 첫 항목의 이 PC 값(Docker 29.9.2, `blobs/sha256` 꼴), `release.yml` 137행의 uv 캐시와 모델 캐시 구분 주석, 머리의 동시 실행 문장, `정리` 단계의 태그 상태 문구, `intro/0.1.0.md`의 마이그레이션 문장, `operations.md` 44행의 이름 여섯.

## 봇 회차

PR 83을 연 뒤 `@coderabbitai review`를 남겼고 `tools/wait_ci.py`로 기다렸다. 헤드 `42a13b5`의 검사가 모두 초록이다(`CodeRabbit`, `claude-review`, `eval-fast`, `eval-full`, `image`, `python`, `standalone`, `ticket`, `title`, `verify`). `standalone` 잡은 초록이지만 실제 시험은 돌지 않았다. `ci.yml`의 `gate` 단계가 PR의 base가 main이거나 main으로의 푸시일 때만 시험을 돌리고, base가 dev인 이 PR에서는 건너뛴 채 성공으로 끝나기 때문이다(24초). claude-review는 지적이 없다. CodeRabbit은 첫 회차에 코멘트 여섯(Major 하나, Minor 다섯)을 냈고, 지적마다 코드와 문서에 대 보았다.

- 고친 것: ① (Major) `지난 판의 공개 릴리스 확인`의 오류 문구가 404만으로 초안과 태그를 지우라고 안내했다. 공개 릴리스 조회는 초안이 있어도 404로 답하고, 이미지 번호 태그가 이미 붙었으면 지운 뒤 전체를 다시 돌릴 때 새 digest를 지키는 차례가 거부한다. `operations.md` 60행이 정한 대로 지우기 전에 레지스트리의 번호 태그를 먼저 보고, 하나라도 붙었으면 전체를 다시 돌리지 않고 남긴 초안으로 끝내라고 문구를 고쳤다. ② `operations.md` 46행과 78행에 실패한 옛 커밋의 실행을 다시 돌려 더 새 커밋의 대기 실행을 밀어내는 예외를 적었다(코드로 읽은 것이고 재 보지 않았다고 함께 적었다). ③ `intro/0.1.0.md`가 정식 0.1.0에도 실리는데 첫 문장이 출시 후보라고만 말했다. 정식과 출시 후보 둘에 맞는 문장으로 고쳤다. ④ 시험의 `_FROM`이 `FROM --platform=…` 줄을 건너뛰어, 고정되지 않은 단계를 더해도 통과했다. 옵션 뒤의 이미지를 읽게 고치고 고정/미고정 입력을 시험에 더했다. ⑤ 워크플로 시험이 `on:` 아래 다른 계기(`repository_dispatch` 등)를 막지 못했다. `on_triggers` 도우미로 계기가 `push` 하나뿐인지 보고, 계기를 더한 입력과 주석 처리한 입력과 `on:` 블록이 없는 입력을 변이 시험으로 고정했다. ⑥ `bake_repositories`가 `["${NAMESPACE}/a:${TAG}", EXTRA_TAG]`처럼 둘째 항목이 변수인 배열을 따옴표 수가 같다는 이유로 통과시켰다. 배열 전체가 허용한 태그 글자 하나와 일치해야 하도록 `fullmatch`로 바꾸고 두 입력을 거부 시험에 더했다.
- 남긴 것(PR 코멘트에 이유를 적었다): `정리` 단계가 `v$NUMBER` 태그를 만든 이를 확인하지 않고 지우는 것(CodeRabbit Minor, `release.yml` 522행). 사전 확인이 이 번호의 태그가 없음을 보고 초안 직후 태그 대조까지 가는 몇 초 구간에서만 열리고, ref에는 만든 이를 알리는 API가 없다. 지우지 않는 쪽으로 바꾸면 초안이 만든 태그가 남아 다음 실행의 사전 확인이 사용자에게 넘기게 된다. 이 설계는 `operations.md`와 agent-os ADR 0056이 정했다. 뒤의 작업으로 넘기는 일이 아니라 근거를 든 보류라 "다음"에 적지 않는다.
- 다시 돌린 것: `ruff check`, `pyright`(오류 0), `zizmor`(지적 없음), `test_release_ci.py`·`test_release_workflow.py`·`test_release.py`·`test_check_notes.py`(`345 passed`). 전체 검사는 이 회차의 커밋이 부르는 pre-commit이 갈음한다.
- 반영으로 새로 쓴 사실 문장: `operations.md` 46·78행의 재실행 예외 문장, `release.yml`의 404 오류 문구, `intro/0.1.0.md`의 첫 문장, `on_triggers`와 `bake_repositories`·`unpinned_from`의 독스트링.
- 둘째 회차(헤드 `42b0ecc`): 검사는 모두 초록이다. claude-review는 지적이 없었다(헌법 patch 승인이 필요하다는 참고만 남겼다). CodeRabbit은 계정 한도로 리뷰하지 못했다(`Review rate limited`). 인라인 코멘트로 보이는 한 건은 첫 회차에서 이미 고친 `on:` 계기 지적이 새 줄 번호에 다시 붙은 것이다. 이 회차부터 Critical·Major만 고치는 규칙이라 고칠 것이 없다. 사용자에게 헌법 1.5.5(문구 수정)의 승인을 물었고 승인을 받았다.

## 회고

후보 일곱을 냈고 판정은 승인 둘, 기각 다섯, 넘김 없음이다. 대기열 만료 후보는 없다(`tools/queue_open_rows.py`가 "만료할 항목 (없음)"을 냈다). 일지는 `tools/sibling_overlap.py --journal`이 이 파일을 가리켰다.

1. **승인: `measured-claim-beyond-probe` 16회차.** 사건은 이 세션이다. `tools/release_ci.py` 독스트링과 시험 머리가 `docker save`의 옛 꼴을 overlay2, `blobs/sha256` 꼴을 containerd 방식으로 갈랐다. agent-os가 자기 PC에서 읽은 분류를 옮긴 것이고, 이 저장소의 개발 PC에서 `docker save`를 한 번 쳐 보지 않았다. 셀프 리뷰는 귀속만 고쳤고 PR 직전 리뷰가 이 PC(Docker 29.9.2, overlay2)의 `blobs/sha256` 꼴로 틀렸음을 보였다. 이미 있는 지침을 어긴 사건이라 회차로 센다. 항목은 이미 5회차를 넘어 chore 배치의 계기다.
2. **승인: `coderabbit-review-turn-limit` 1회차(새 항목).** 사건은 이 세션이다. PR 직전 리뷰 서브에이전트가 CLI 리뷰를 끝낸 뒤 트리아지하다가 `maxTurns: 40`에 걸려 보고 없이 멈췄고, `SendMessage`로 다시 불러 보고를 받았다(도구 호출 58번, 536초). 정의에 턴 예산이 없다. 처방은 `.claude/agents/coderabbit-review.md`에 턴 예산 한 줄이다. 더하는 것이라 다섯 번째에 반영한다.
3. **기각: 리뷰가 제 몫을 한 것.** CodeRabbit이 첫 회차에 낸 여섯이다. 404 오류 문구의 빠진 단계(Major), 재실행 예외 문장, 소개 글의 출시 후보 표현, 판정 함수의 입력 꼴 셋(`FROM --platform`, `on:`의 다른 계기, bake 태그 배열)이다. 모두 이 PR 안에서 코드와 시험으로 고쳤다. 입력 꼴 셋은 변이 짝이 없었던 것이 아니라 짝이 덮지 못한 꼴이라 `repo-state-test-without-mutation-partner`의 사건이 아니다.
4. **기각: 앱의 워크트리 가드가 거절한 명령.** "git"이 든 경로와 heredoc, `.github`가 든 zizmor 명령을 가드가 거절했고 PowerShell과 Write 도구로 바꿔 갔다. 가드가 그 자리에서 막았다.
5. **기각: 이미 있는 훅이 알린 것.** 한글 폭 때문에 `ruff` 줄 길이를 넘긴 알림 여러 건, 중간 턴에 한국어로 쓰라는 알림, 인용 대조의 옛 문장 인용 경고 둘이다. 알림대로 바로 고쳤다.
6. **기각: 편집 도중의 낡은 진단.** IDE의 pyright 진단이 편집 순서 사이에 "정의되지 않음"을 여러 번 냈지만 `uv run pyright`는 오류 0이었다. 도구의 일시 표시이고 처방할 규칙이 없다.
7. **기각: 코드래빗 한도.** 둘째 회차 CodeRabbit이 계정 한도로 리뷰하지 못했다. 병합 절차(`merge.md`)가 이미 한도를 실패로 세지 않는 길을 정했다.

반영 자리는 모두 대기열이다. 이 세션에서는 하네스를 고치지 않았고 항목 파일 하나의 줄과 새 항목 파일 하나만 더했다.

## 다음

이 PR(base dev)을 병합하면 release-image의 티켓 여덟이 모두 `done`이고 기능 계획에 `**끝:** 2026-11-20`이 서서 기능이 `done`이다. 제품 코드와 계약은 바꾸지 않았다. 헌법은 문구 수정으로 1.5.5가 됐고 사용자가 승인했다.

병합 뒤 `next-session` 결정표를 읽으면 순서는 이렇다.

1. **출시 PR 계기가 선다.** 끝 줄을 적은 커밋이 dev에만 있고 열린 출시 PR이 없으며 dev가 main을 품었다(`git merge-base --is-ancestor origin/main origin/dev`가 0). 그러나 전제 확인 4(릴리스의 사람 몫)가 어긋난다. 2026-11-20에 읽기 전용으로 본 값은 GitHub 환경 `release`가 404이고 Docker Hub `njh6803/rag-engine-server`가 404다. 그러면 출시 PR을 열지 않고 `출시 보류: 릴리스의 사람 몫` 한 줄을 보고에 쓴다. 전체 게이트(전제 확인 3)의 수동 실행은 이 보류가 서면 돌리지 않는다. 사람 몫은 이 일지 위의 "사람 몫" 절과 PR 본문의 "리뷰어 참고"에 있다. 비밀 값은 사용자가 직접 넣는다.
2. **그다음 줄은 하네스 chore 배치다.** 이 기능의 마지막 티켓이었고 대기열에 회차 5 이상인 열린 항목이 열다섯이다(`tools/queue_open_rows.py`의 "회차 5 이상" 줄: `measured-claim-beyond-probe`(16회차), `crlf-from-script-edits`, `mutate-marker-discovery`, `review-report-journal-lag`, `docs-only-commit-full-pytest`, `commit-msg-after-slow-checks`, `decision-word-residue`, `python-i-utf8`, `extract-asks-tool`, `gate-masked-by-echo-chain`, `grilling-premise-check`, `precommit-mutations-after-tests`, `check-quotes-verbatim-paste`, `edit-during-precommit`, `rename-sweep-misses-forms`). 같은 대상 파일의 항목끼리 묶고 대상 파일이 겹치지 않는 티켓만 나란히 연다.
3. **그 뒤 프론티어는 source-sync다.** core와 release-image가 모두 done이라 막는 기능이 없다. 기능 계획의 `**설계:**` 줄을 먼저 본다.

사람이 설정을 마친 뒤 출시 PR이 서면, 첫 릴리스는 그 병합이 main을 움직일 때 `release.yml`이 처음 돈다. 그 병합을 한 세션이 `merge.md`의 "릴리스를 기다린다"로 끝까지 보고 티켓 08의 Further Notes에 셋을 적는다. 모델 캐시를 읽었는지, 두 이미지 층이 한 번만 저장됐는지, 노트의 "계약의 판" 절이 `--version` 줄과 같은지다. 이어 받은 묶음(`rag-engine-<번호>.tar.gz`)과 Docker Hub 이미지(`njh6803`)로 단독 compose 시험을 한 번 더 돈다. 빈 `DOCKER_CONFIG`로 로그인 없이 이미지가 받히는지도 함께 본다.

뒤로 넘긴 일은 아래 넷이다.

- 04 PR에서 미룬 Minor: `tests/tools/test_deploy_guide.py`의 폐쇄망 시험이 로컬 이름(`rag-engine-offline/…`)을 글자 그대로 박았다. 바깥 이미지의 digest를 바꾸는 변경이 오면 안내와 함께 고친다. 이 PR은 바깥 이미지를 바꾸지 않았다.
- 원격 브랜치 `feature/04-install-guide-walks-operator`가 지워지지 않았다. 권한 분류기가 삭제를 거부했고 우회하지 않았다. 사람이나 지워도 된다고 허락한 세션이 지운다.
- 이 PR이 남긴 Minor: 취소나 제한 시간으로 `publish`가 초안을 남기면 이어지는 푸시의 `build`가 최대 80분을 쓰고 지은 뒤에야 사전 확인에서 막히는 낭비(agent-os와 같은 구조). 단계 이름의 옛 낱말 `판`. `정리` 단계가 이 실행이 만들지 않은 태그를 지울 수 있는 좁은 구간(CodeRabbit Minor. 태그에는 만든 이를 알리는 API가 없어 남겼다). 첫 릴리스를 보며 고칠 필요가 드러나면 다음 티켓이 다룬다.
- 리눅스에서 처음 도는 것: `ci.yml`의 단독 compose 시험은 base가 dev인 PR에서 건너뛰므로, 실제 시험은 출시 PR(dev→main)이나 main 푸시에서 처음 리눅스 러너로 돈다. `release.yml`의 `build` 잡(이미지 짓기와 점검과 올리기)과 `publish` 잡도 아직 어느 러너에서도 돈 적이 없다.

세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
