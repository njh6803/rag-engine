# 핫픽스 standalone-test-fills-image-namespace: 릴리스 워크플로의 단독 compose 시험이 시험용 이미지 이름으로 묶음을 띄우게 고친다 · 2026-11-20

release-image의 첫 릴리스(출시 PR 84의 병합 커밋 `24f814d`)가 `build` 잡의 `단독 compose 시험`에서 실패해 그 고침을 같은 세션에서 이어 했다. 브랜치는 `hotfix/standalone-test-fills-image-namespace`(기준 `origin/main`), 작업은 `08-ci-releases-from-main` 워크트리에서 했다. 모델은 Sonnet 5.5 / high이다. 레지스트리와 GitHub에는 올라간 것이 없다(Docker Hub 태그, GitHub 릴리스, git 태그를 모두 읽어 비었다). 준비, 한 일, 확인한 것, 셀프 리뷰, 남은 것을 차례로 두고, PR과 병합과 릴리스 결과는 그 뒤에 잇는다.

## 준비

- 실패한 실행 https://github.com/njh6803/rag-engine/actions/runs/44716196490 의 로그를 읽었다. `docker compose up -d --wait`이 종료 1이고 시작부터 끝까지 약 20초였다. 컨테이너 로그(`compose.log`)는 0바이트였고 stderr는 로그에 없었다(시험의 `run`이 삼킨다).
- 원인은 이렇게 보았다. 올릴 묶음은 `njh6803`으로 짓고 시험용 이미지는 `rag-engine-release-test/…`로 지어 러너에 싣는다. 시험이 `.env`에서 두 칸만 채워 `RAG_ENGINE_NAMESPACE=njh6803`이 그대로 남았다.

## 한 일

- `tests/standalone/test_standalone_compose.py`: `.env` 채우기를 `write_env(directory, namespace, version, password)`로 뺐다. 채우는 칸 넷은 순수 함수 `env_values`가 정하고, 이름공간과 번호를 시험이 받은 값으로 덮어쓴다. `run`이 실패하면 stdout과 stderr를 메시지에 싣는 `CommandFailed`(`CalledProcessError`의 하위 클래스)를 던진다. 모듈 독스트링의 "운영자와 다르게 하는 일"을 둘에서 셋으로 고쳤다. 기존 시험 `test_빈_필수_값이면…`이 손으로 적던 네 칸을 `env_values`로 바꿨다.
- `tests/tools/test_standalone_env.py`(새 파일): 단독 시험 모듈을 경로로 불러 `env_values`, `write_env`, `run`을 Docker 없이 본다. `tests/standalone/`이 기본 수집에서 빠지므로 `tests/tools/`에 뒀다. 표지 상수는 `tools/release.py`의 것을 쓴다.
- `.scratch/harness/issues/standalone-test-fills-image-namespace.md`: 티켓과 Comments.
- `release.yml`과 `ci.yml`은 바꾸지 않았다. 워크플로가 같은 시험을 같은 환경 변수로 부른다.

## 확인한 것

- 고치기 전에 시험이 빨갰다: 새 시험 다섯 중 셋이 빨갛다. `env_values`가 없다는 `AttributeError` 둘과, `str(CalledProcessError)`에 stderr 표지가 없다는 단언 실패 하나다. 표지는 명령 줄에 그대로 들지 않게 두 토막으로 쪼갰다(그대로 두면 명령 부분만으로 단언이 지난다).
- 이 PC에서 틈을 되풀이했다. 고치기 전 픽스처와 같게 두 칸만 채워 `docker compose up`을 치면 `manifest for njh6803/rag-engine-server:0.1.0-rc.1 not found: manifest unknown`으로 종료 1이다. 첫 릴리스의 원인이 같다고 확정한 것은 아니고 같은 자리에서 같은 코드로 멈춘 것까지다.
- 고친 뒤 환경 변수 경로(이름공간 `rag-engine-test`, 묶음은 `njh6803`)로 `tests/standalone`을 돌렸다. `up`을 지나 `2 failed, 23 passed in 758.17s`였고, 실패한 둘(MCP 검색의 `ReadTimeout` 60초, 서버 프로세스를 죽인 뒤 회복 20.8초 대 상한 15초)만 다시 돌리니 `2 passed in 335.04s`였다. 다른 세션이 이 PC를 쓰는 때라 CPU가 80%대였다. 한 번에 전부 통과한 실행은 얻지 못했다. 앞서 한 번은 같은 부하로 서버 건강 검사가 늦어 `up`이 `server-1 is unhealthy`로 실패했고, 그 문구를 읽을 수 있었던 것이 `run` 고침의 효과다.
- 커밋의 pre-commit 첫 시도에서 pytest가 `2 failed, 4937 passed in 1236.17s`였다. 실패는 `tests/test_serve_command.py`(서버가 30초 안에 뜨지 않았다)와 `tests/app/test_job_lease.py`(처리 5.7초 대 상한 5초)로 둘 다 시간 상한이고, 이 변경이 닿지 않는 코드다. 둘째 시도는 `1 failed, 4938 passed in 887.44s`로 `test_serve_command.py`의 같은 시험이 같은 문구로 졌다. 그 파일을 홀로 돌리면 `2 passed in 10.58s`(그 시험의 호출이 9.74초)였다. 다른 세션이 이 PC를 쓰며 CPU가 60~80%대였고 전체 실행은 평소 7.5분 남짓인데 15~20분이 걸렸다. 부하에서만 지는 시간 시험이라 새 항목을 만들지 않고 이 일지에만 남긴다.
- `ruff check .`, `ruff format --check .`, `pyright`(오류 0), `lint-imports`(2 kept), `tools/check_type_escapes.py`가 초록이다. 테스트는 커밋의 pre-commit이 갈음한다.

## 셀프 리뷰

`/code-review`를 기준 `origin/main`(`24f814d`)으로 돌렸다. 범위는 고친 파일 하나, 새 파일 둘, 커밋 없음이다. 표준 축은 Major 하나와 Minor 다섯과 Nit 둘, 명세 축은 Major 하나와 Minor 몇 개를 냈다.

- 고친 것: ① `env_values`가 운영자의 `.env` 채우기와 같다고 적은 것은 거짓이었다. `.env.example`이 두 칸을 "고치지 않는다"고 적는다(Major). 독스트링과 모듈 독스트링, 티켓을 고쳤다. ② 픽스처가 옛 두 칸 채우기로 돌아가도 새 시험이 초록이던 틈(명세 축 Major)은 `.env` 쓰기를 `write_env`로 빼고 그 함수를 시험해 닫았다. ③ 원인을 사실처럼 적던 문장을 이 PC에서 되풀이한 값으로 바꾸고 추정임을 티켓에 남겼다. ④ 항상 참인 단언 `"3" in str(...)`을 `"exit status 3"`으로 바꿨다. ⑤ 시험이 손으로 다시 구현하던 표지 치환을 `tools.release`의 상수로 바꿨다. 같은 네 칸을 적던 기존 시험도 `env_values`를 쓴다. ⑥ 지금 코드 경로에 없는 옛 호출을 재던 시험을 지웠다.
- 남긴 것: 실패 메시지에 stdout 전체가 실려 길게 출력하고 실패한 호출의 로그가 길어진다. 묶음 안 `.env.example`의 이름공간이 틀려도 이 시험은 이제 잡지 못한다. `tests/tools/test_release.py`가 표지 치환을 따로 잰다.
- 다시 돌린 것: 위 `확인한 것`의 검사 다섯. 전체 리뷰는 다시 돌리지 않았다.

## PR 직전 리뷰

CodeRabbit CLI(`coderabbit-review` 서브에이전트)는 권한 분류기가 실행을 거절해 돌지 못했다(사유는 민감한 정보 유출, diff가 외부 서버로 나가는 실행이라 사용자가 정할 일이고 우회하지 않았다). 한도 소모는 없다. 그 자리를 대체 둘이 맡았다: 내장 `/security-review`와 `bug-perf-review` 서브에이전트(기준 `origin/main`, 커밋 하나, 파일 넷). CodeRabbit의 판정이 아니라는 점을 보고에 남긴다.

- `/security-review`: 지적 없음. 변경이 시험 코드와 문서뿐이고, `CommandFailed`가 싣는 값은 시험이 띄운 일회성 스택의 것이다.
- `bug-perf-review`: Critical과 Major 없음, Minor 하나와 Nit 둘이다. 유효한 지적 셋은 모두 반영하거나 판정했다. 서브에이전트는 릴리스 워크플로 경로(환경 변수 셋)와 `ci.yml` 경로(환경 변수 없음)에서 이 고침이 맞음을 함수와 호출로 대 봤고, `check=False` 호출이 달라지지 않았고 `str(CommandFailed)`가 음수 종료 코드와 `stdout=None`에서도 터지지 않음을 호출로 쟀다.
- 고친 것: ① 새 시험의 한글 표지가 `PYTHONUTF8`이 없는 Windows 셸에서 자식 stderr가 cp949로 나가 깨져 빨개졌다(서브에이전트가 그 환경 변수를 빼고 돌려 `1 failed`를 봤다). 표지를 ASCII로 바꿨다. ② 이 일지와 티켓이 토큰이 실패 경로 로그에 남을 수 있다고 쓴 것은 과장이었다. `_bootstrap_token`은 종료 0일 때만 토큰을 stdout에 낸다(`src/rag_engine/main.py`를 읽어 확인했다). 두 문장을 고쳤다.
- 남긴 것: `CommandFailed`가 stdout 전체를 싣는 분량 문제는 원인을 읽는 쪽 이득이 커서 그대로 둔다. `stack` 픽스처가 `write_env`를 부르는지 자체는 Docker 없이 재지 못한다(셀프 리뷰가 이미 닫은 한계).
- 서브에이전트가 짚은 이상 하나: 새 시험 5건이 처음 두 번의 전체 실행에서 `5 passed in 143s`였는데 시험별 소요는 1초 미만이었고, 이후 같은 파일은 `1.13s`였다. 이 PC의 부하나 첫 실행의 캐시로 보이지만 원인은 확인하지 못했고 저장소 코드의 문제로 재현되지 않았다. 병합 전 pre-commit의 pytest에서는 이 파일이 다섯 건 모두 통과했다.
- 다시 돌린 것: `ruff`, `pyright`, 새 시험(표지를 바꾼 뒤)은 커밋의 pre-commit이 갈음한다.

## 커밋과 PR

- 커밋 둘: 고침 본체(`f3444f6`)와 PR 직전 리뷰 반영(`5f403ed`). 후속 커밋의 pre-commit은 첫 시도에서 부하 때문에 시험 둘이 졌다(`tests/test_serve_command.py`의 서버 시작 30초, `tests/contract/test_search_tool.py`의 MCP 연결 오류). 두 파일을 홀로 돌리면 7건이 통과했고(458초로 평소보다 한참 느렸다), 코드를 바꾸지 않은 재시도에서 통과해 커밋이 들어갔다. 부하에서만 지는 시간 시험이라 새 항목은 만들지 않는다.
- PR 88을 `hotfix/*`에서 main으로 열었다. 형제 겹침 검사(`sibling_overlap.py`)는 번호 겹침 없음이고, 다른 워크트리 `glossary-release-number-names`가 같은 파일 `tests/standalone/test_standalone_compose.py`를 고치는 중이라 나중에 병합하는 쪽에서 글자 충돌이 날 수 있다는 것만 알렸다.

## PR 봇 회차

첫 회차(머리 `5f403ed`): 검사 아홉이 모두 초록이고 CodeRabbit은 지적 없음으로 끝났다. claude-review가 Minor 하나와 Nit 하나를 냈다.

- Minor(고쳤다): `write_env`를 직접 부르는 시험의 주석이 픽스처가 옛 두 칸 채우기로 돌아가면 이 시험이 빨개진다고 적었지만 시험은 픽스처가 그 함수를 부르는지 보지 않는다. 이 한계는 PR 본문과 이 일지에 적혀 있었는데 코드 주석만 반대로 적었다. 주석과 `write_env`의 독스트링을 한계대로 고쳤다.
- Nit(보류): 시험이 기본 수집에서 뺀 모듈을 경로로 불러와 수집 때 실행한다. 그 모듈 최상위에 환경 변수 읽기나 skip이 늘면 `tests/tools/` 수집이 깨질 수 있다. 순수 함수를 `tools/` 쪽 모듈로 옮기면 해결되지만 지금은 단독 시험 모듈이 그대로 쓰는 함수라 옮기면 둘이 갈린다. 후속으로 둔다.
- 뒤로 넘긴 일: 위 Nit(`env_values`·`write_env`·`run`·`CommandFailed`를 `tools/` 모듈로 옮겨 경로 import를 없앤다)을 아래 `다음`에 적었다.

## 회고

- 낸 후보: 둘. 승인 1(대기열 항목으로), 기각 1. 넘김 0.
- 승인: `release-workflow-first-run-on-main`(1회차). 사건은 첫 릴리스가 main에서 처음 돌다 단독 시험에서 멈춘 것이다. 환경 변수 경로와 `build` 뒤쪽 단계가 병합 전에는 어떤 검사도 밟지 않았다. 층은 검사(CI 잡)로 정했고, 더하는 것이라 다섯 번째에 반영하며 레지스트리에 올라간 것이 없어 손상으로 세지 않았다. 대기열 항목으로 두었다.
- 기각: 내가 쓴 주석이 시험이 지키지 않는 약속을 적은 것. 셀프 리뷰가 같은 꼴(운영자와 같다는 거짓 서술)을 이미 잡았고 이번에도 PR 봇 리뷰가 잡아 리뷰가 제 몫을 한 사건이다. 사건 셈에서 뺀다.
- 일지에만 남기는 것: 이 PC의 부하로 시간 상한이 걸린 시험의 새 사례 셋(`tests/test_serve_command.py`, `tests/app/test_job_lease.py`, `tests/contract/test_search_tool.py`). 부하 시간 시험은 사용자가 닫은 채 두기로 한 종류라 새 항목을 만들지 않는다. CodeRabbit CLI 실행을 권한 분류기가 거절한 것은 앱 가드가 그 자리에서 막은 것이라 기각이다.
- 대기열 `review-report-journal-lag`: 이번 세션은 셀프 리뷰와 PR 직전 리뷰의 보고를 받은 턴 가까이 일지에 옮겼으나 컨텍스트 압축이 끼어 그 시점은 재지 못했다. 회차를 더하지 않는다.
- 만료할 항목: 이 회고에서 `queue_open_rows.py`를 같은 낱말(standalone, release.yml, namespace)로 돌렸다. 만료 후보는 확인하지 않았다(이 핫픽스 범위 밖).

## 다음

- 이 PR(88)의 CI와 봇 회차는 끝났다. 병합하면 릴리스 워크플로가 같은 번호 `0.1.0-rc.1`로 다시 돈다. 병합한 세션이 `릴리스: 병합 커밋 <해시>` 코멘트를 달고 실행을 끝까지 보며 `결과:`를 기록한다. 이 실행이 `build` 뒤쪽 단계(`점검`, `노트 짓기`, Docker 로그인, `이미지 올리기`, 시험한 이미지와 올린 이미지 대조, `publish`)를 처음 밟으므로 거기서 실패하면 `docs/constitution/operations.md`의 실패 표를 따른다. 직전 릴리스가 남긴 초안이 있으면 `점검`이 막으니 사용자에게 지워 달라고 한다.
- 병합과 릴리스 뒤 main을 dev에 합치는 PR(85)이 열려 있다. `verify`가 새 머리에서 초록이면 merge 커밋으로 병합한다.
- Nit 후속: 단독 시험 모듈의 순수 함수(`env_values`, `write_env`, `run`, `CommandFailed`)를 `tools/` 모듈로 옮겨 `tests/tools/test_standalone_env.py`의 경로 import를 없앤다. 급하지 않다.
- 대기열 `release-workflow-first-run-on-main`: 릴리스가 처음 끝까지 도는 모양을 본 뒤, 병합 전에 같은 길을 밟는 검사의 모양을 고른다.
- 남은 사람 몫과 들고 있는 것: 원격 브랜치 `feature/04-install-guide-walks-operator`가 남아 있다(지우는 푸시를 권한 분류기가 거절했다). 주 체크아웃은 갱신하지 않았다(`origin/dev`보다 뒤). 스크래치의 `models_flat/`(4.3GB)은 끝나면 지운다. 열지 않은 chore 지시문 넷은 스크래치패드의 `directives_held_2to5.md`에 있다.
