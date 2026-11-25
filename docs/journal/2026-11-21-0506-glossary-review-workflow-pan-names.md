# glossary-review-workflow-pan-names: 리뷰 워크플로 주석의 판 두 곳을 버전으로 바꾼다 · 2026-11-21

PR 90(일지 `2026-11-20-2107-glossary-standalone-pan-names.md`)을 병합한 같은 세션이 그 일지 "다음"의 첫째 일을 이어서 한 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-review-workflow-pan-names.md`, 브랜치는 `chore/glossary-review-workflow-pan-names`이고 `origin/dev`(`172b8cd`, PR 90까지 든 것)에서 새로 땄다. 용어집의 이름을 agent-os의 결정에 맞추는 일의 열한 번째 PR이다. 셀프 리뷰 이후의 절은 PR을 연 뒤 이어 쓴다.

## 계기

PR 90 병합 보고의 끝에서 사용자에게 `claude-code-review.yml`의 판 두 줄을 고치는 작은 PR을 이 세션에서 이어 낼지 물었고 "네, 이어서"라고 답했다. 요청 범위는 PR과 병합까지다. 이 파일을 바꾸는 PR은 일지·대기열·티켓·하네스 탐침 밖의 파일을 함께 싣지 못하므로(같은 파일 95~127행의 `Fail when Claude left no comment` 스텝, 허용 정규식은 119행) 앞 영역(PR 90)과 따로 낸다.

## 한 것

- `.github/workflows/claude-code-review.yml` 21행 `판은 손으로 올린다`를 `버전은 손으로 올린다`로, 87행 `판이 바뀌면`을 `버전이 바뀌면`으로 바꿨다. 둘 다 주석이다. 21행은 리뷰 액션의 번호이고 87행은 액션을 올리면 바뀌는 Claude Code의 번호다. 이 파일에 남은 `판`은 75·77·78행의 `판단`뿐이다.
- 티켓 `.scratch/harness/issues/glossary-review-workflow-pan-names.md`를 썼다.
- 대기열 `glossary-plain-names-left`에 이 영역을 한 문단 더했다. 31행이 남은 일로 적은 이 두 줄이 끝났고, 홀로 쓰인 판은 마지막 영역의 몫만 남았다. 앞 영역의 Nit(`deploy/standalone/compose.yaml` 78행 `CPU 버전`은 이미지의 종류를 가리켜 `CPU 이미지`가 낫다는 지적)을 마지막 영역에 맡긴다고 적었다.
- 헌법은 건드리지 않았다. 주석 두 줄이라 헌법 버전은 1.5.7 그대로다.

## 검증

- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 새 번호 없음, 함께 고친 파일 없음. 형제가 쓴 가장 높은 헌법 버전은 1.5.7(`origin/dev`)이다.
- YAML이 그대로 읽힌다(`yaml.safe_load`로 읽어 잡 `claude-review` 하나가 나왔다).
- `git diff`는 파일 하나, 두 줄 추가, 두 줄 삭제다. 이 파일을 인용하는 시험은 `tests/`에 없다(`claude-code-review`와 옛 문구를 `tests/`에서 grep해 0건).
- 전체 pytest와 나머지 훅은 커밋이 부르는 pre-commit의 검사 러너가 돈다. `zizmor`를 포함한 CI의 파일 검사는 PR에서 본다.

## 셀프 리뷰

`code-review` 스킬로 기준 `172b8cd`(`origin/dev` 끝)에서 수정 1개 파일, 미추적 1개(티켓), 커밋 0개를 두 축으로 봤다(일지는 이 시점에 아직 없었다). 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical과 Major는 없었고 Minor 넷이 나왔다.

**고친 것.**
- 표준·명세 축 Minor(같은 지적). 티켓이 가드를 "일지·티켓·프로브 밖의 파일을 함께 싣지 못하는 검사"로 적었는데 실제 허용 집합에는 대기열 폴더가 든다. 앞 티켓의 문구를 옮겨 온 좁은 요약이었다. "일지·대기열·티켓·하네스 탐침"으로 고치고 같은 파일의 95~127행을 댔다.
- 표준·명세 축 Minor(같은 지적). 티켓이 87행의 판을 "액션의 번호"로, 첫 문단에서는 "도구나 이미지의 번호"로 적었다. 이 두 곳에 이미지는 없고 87행은 액션을 올리면 바뀌는 Claude Code의 번호다. 고쳤다.
- 표준 축 Minor. 앞 영역 PR 79·87·90이 모두 대기열 `glossary-plain-names-left`를 고쳤는데 이 티켓은 `대기열:`을 달고도 그 항목을 갱신하는 수용 기준이 없었다. 가드가 대기열 경로를 허용하므로 기준을 더하고 항목에 문단을 더했다.

**남긴 것과 이유.** 없음.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장).**
- 티켓: 같은 파일의 95~127행 스텝이 일지·대기열·티켓·하네스 탐침 밖의 파일을 함께 싣지 못하게 한다.
- 티켓: 87행의 판은 액션을 올리면 바뀌는 Claude Code의 번호를 뜻한다.
- 대기열 새 문단: `deploy/standalone/compose.yaml` 78행의 `CPU 버전`은 이미지의 종류를 가리킨다는 지적이 있었고, 미룬 두 줄은 `tests/tools/test_check_notes.py` 875행과 `.claude/skills/code-review/SKILL.md` 108행이다.

**다시 돌린 명령.** 고친 글은 문서뿐이다. 아래 "커밋"의 pre-commit 결과가 갈음한다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 거부되어(앞 PR들과 같다) 버그·성능 축은 `bug-perf-review` 에이전트로, 보안 축은 변경을 직접 읽어 대신했다.

**보안.** 지적 없음. 워크플로에서 바뀐 것은 `#` 주석 두 줄이고 `claude_args`, `run`, `env`, `permissions`, `${{ }}` 표현식, 허용·거부 도구 목록은 그대로다. 87행의 주석은 `claude_args: >-` 바로 위라 값 안에 들어가지 않는다.

**버그·성능(`bug-perf-review`).** 유효 1, 오탐 0. Critical·Major 없음. 이전과 이후 파일을 글자 단위로 맞댔고 바뀐 글자는 21행과 87행의 `판`→`버전`뿐이었다. 밀 주장(95~127행 스텝의 허용 집합, 87행의 Claude Code 번호, `CPU 버전`이 TEI 이미지 태그를 가리킴, 미룬 두 줄의 위치, 헌법 버전 1.5.7)이 모두 맞았다.

**고친 것.**
- Minor. 대기열 새 문단이 마지막 영역의 파일 묶음 전체에 홀로 쓰인 판이 있는 것처럼 읽혔다. 실제로 홀로 쓰인 판이 든 곳은 `src/`, 평가 묶음, `README.md`뿐이고, `GLOSSARY.md`는 옛 이름을 적은 `_Avoid_` 줄뿐이며, `docs/constitution/operations.md`와 PR 서식에는 색인 판 계열과 agent-os ADR 0056의 결정 이름 인용(남길 것)만 있다. 그렇게 가르도록 문단을 고쳤다. `operations.md`의 판 줄은 직접 다시 읽어 맞다고 확인했다.

**남긴 것.** 없음.

**다시 돌린 명령.** 고친 글은 문서뿐이다. 아래 "커밋"의 pre-commit 결과가 갈음한다.

## 커밋

브랜치 `chore/glossary-review-workflow-pan-names`에서 커밋 `2848a6b`(제목 `chore: 리뷰 워크플로 판을 버전으로 바꾼다 (harness glossary-review-workflow-pan-names)`, 71자)를 냈다. 파일 넷(워크플로, 티켓, 대기열 항목, 일지)을 담았다. 시도는 한 번이었고 pre-commit이 650.3초에 통과했다(pytest 649.9초, pyright 36.2초, run-hooks 42.1초). 푸시 전에 `git fetch origin`과 `git merge-base --is-ancestor origin/dev HEAD`로 `origin/dev`(`172b8cd`)를 품은 것을 보고 그대로 올렸다.

## PR 봇 회차

PR 91을 `dev`로 열고 마지막 푸시 뒤에 `@coderabbitai review`를 남겼다. 대기(`tools/wait_ci.py 91`) 결과는 헤드 `2848a6b`에서 모든 검사가 통과였다(`python`, `image`, `ticket`, `standalone`, `eval-fast`, `eval-full`, `verify`, `claude-review`).

- claude-review: 이 워크플로 파일을 바꾼 PR이라 액션이 건너뛰고 스텝이 파일 집합만 본다. 성공으로 끝났고 리뷰 코멘트는 없다. 이 PR의 실질 리뷰는 위 셀프 리뷰와 PR 직전 리뷰다.
- CodeRabbit: `Review rate limited`(무료 리뷰 한도)로 리뷰가 없었다. 한도에 걸린 것은 통과로 세는 규칙대로 기다리지 않았다. 리뷰를 받은 커밋은 없다.

반영할 지적이 없어 고친 커밋은 없다. 보류한 지적도 없다.

## 회고

후보 2개를 냈고 판정은 승인 1, 기각 1, 넘김 0이다. 일지와 이 세션을 읽었고, 대기열은 `uv run python tools/queue_open_rows.py`로 읽었다(열린 항목 72개, 만료할 항목 없음).

- 후보 1. 주석 두 줄과 기록만 바꾼 커밋의 pre-commit이 전체 pytest를 649.9초 돌았다. 승인(이미 처방한 사건). 열린 항목 `docs-only-commit-full-pytest`가 같은 사건을 처방하고 있어 9회차로 더했다. 항목은 게이트를 좁히는 일이라 넘김 대상으로 이미 사용자가 대기열에 두기로 답했고, 회차 5 이상이라 chore 계기 조건에 이미 들었으므로 새 항목을 쓰지 않았다.
- 후보 2. 티켓이 같은 파일 가드를 "일지·티켓·프로브 밖의 파일"로 적은 것은 앞 티켓의 문구를 옮긴 좁은 요약이라 대기열 폴더가 빠졌다. 기각. 셀프 리뷰 두 축과 PR 직전 리뷰가 모두 잡았다. 리뷰가 제 몫을 한 사건이라 회차로 세지 않고, 반례를 일반 조항으로 올려야 하는 닫힌 목록도 아니다(허용 집합은 한 줄이고 119행이 원천이라 티켓은 그 줄을 댄다).

반영한 것은 없어서 티켓에 `회고 반영` 줄을 더하지 않았다.

## 다음

병합은 이 세션이 이어서 한다. 병합 직전에 `git fetch origin`과 `git merge-base --is-ancestor origin/dev HEAD`로 뒤처졌는지 보고, `tools/sibling_overlap.py`와 `headRefOid` 대조를 거친다. 병합 결과(`주 체크아웃 미갱신` 한 줄 포함)는 일지가 아니라 병합 보고에 적는다.

용어집 이름 맞추기에 남은 일은 하나다.

1. 마지막 영역 PR: 홀로 쓰인 판이 든 `src/`와 검색 평가 묶음(`tools/search_eval.py`, `tests/tools/test_search_eval*`, `compose.eval.yml`)과 `README.md`, `GLOSSARY.md`(버전 항목을 이미지와 도구의 번호까지 넓히고 "버전 칸"의 예외를 적는다. 홀로 쓰인 판은 옛 이름을 적은 `_Avoid_` 줄뿐이라 남긴다), 색인 판 계열(`tests/tools/test_check_notes.py` 875행, `.claude/skills/code-review/SKILL.md` 108행, `docs/constitution/operations.md` 38행과 PR 서식 35행의 "색인 판" 포함). `deploy/standalone/compose.yaml` 78행 `CPU 버전`은 `CPU 이미지`가 낫다는 Nit(PR 90의 claude-review)를 이 영역이 이미지 종류를 가리키는 판을 다시 볼 때 같이 본다. `operations.md`의 agent-os ADR 0056 결정 이름 인용은 남길 것이다. 사용자가 색인 판은 버전으로 바꾼다를 이미 골랐다. 이 영역이 끝나면 대기열 `glossary-plain-names-left`(사람 몫)를 닫는다.

이 세션의 정리 남은 일: `tidy-checkouts` 때 거부된 `remove-branch worktree-04-install-guide-walks-operator`, 건너뛴 `empty-trash`, 넘긴 `14-reindex-version-switch` 워크트리. 테스트용 PostgreSQL 컨테이너(`rag-engine-test-postgres-1`)는 켜 둔 채다.
