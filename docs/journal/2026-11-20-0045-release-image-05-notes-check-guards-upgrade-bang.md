# release-image 05: 노트 검사가 업그레이드 느낌표를 지키게 한다 · 2026-11-20

release-image 티켓 여덟 가운데 넷째로 구현한 티켓(`05-notes-check-guards-upgrade-bang`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/05-notes-check-guards-upgrade-bang.md`이고 브랜치는 `feature/05-notes-check-guards-upgrade-bang`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, PR 직전 리뷰, 커밋, 다음을 차례로 둔다.

## 준비

- 지시문대로 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 맞췄다. 주 체크아웃은 갱신하지 않았다(`tidy-checkouts`는 이 묶음의 첫 세션 몫이다).
- 시작할 때 agent-os 변경을 봤다. `git -C C:/project/agent fetch origin`이 종료 0이었고 티켓이 적은 `git log b74a8adf2..origin/dev -- <경로 열 개>`는 종료 0에 출력이 비어 사용자에게 묻지 않았다. 옮긴 원본은 agent-os `1aac0cf`의 `tools/check_notes.py`와 그 시험이다.
- 06과 02가 남긴 일을 이 티켓이 맡았다. `docs/constitution/operations.md`에 남은 문장 가운데 05가 들인다고 미래형으로 적은 것이 두 군데였고, 사용자에게 걷는 초안을 물어 "고친다 (patch 한 칸)"를 받았다. 걷은 뒤 헌법 판을 1.5.3에서 1.5.4로 올렸다.
- 같은 문서의 `claude-code-review.yml`에 07이 더한다는 문장도 낡았지만(07은 병합됐다) 사용자가 승인한 두 문장이 아니라서 건드리지 않았다. 아래 "다음"에 적는다.

## 한 일

티켓의 수락 기준 열한 줄 가운데 아홉 줄을 채웠다. 나머지 둘(병합 전 squash 설정 확인, CI 실행 주소)은 PR을 연 뒤에 닫는다.

- `tools/check_notes.py`(새 파일): agent-os의 판정 셋을 옮겼다. (가)는 제목의 꼴과 느낌표와 `upgrade/` 원고의 짝, (나)는 기능 단락의 빠뜨림, (다)는 원고의 꼴이다. 모드는 셋(인자 없음은 (나)(다), `--ci`는 셋 모두, `--title-only`는 (가))이고 표준 라이브러리만 쓴다. 머리 브랜치가 `main`이나 `dev`면 건너뛰고 핫픽스는 건너뛰지 않는다. 막는 글과 독스트링은 이 저장소의 이름으로 고치고, 가리키는 절은 06이 정한 "릴리스 노트 원고"다.
- (가)에 마이그레이션 판정을 더했다. `src/rag_engine/adapters/postgres/migrations/versions/` 아래 `.py`를 더하거나 고치거나 지우거나 옮기면 제목에 느낌표가 있어야 한다. 경로만 본다. 이름 바꾸기는 `--no-renames`로 지움과 더함 둘로 세어 옛 경로와 새 경로를 모두 본다.
- `tests/adapters/test_migration_heads.py`(새 파일): 이 저장소의 마이그레이션 폴더에서 alembic head가 하나임을 재고, 같은 부모를 가리키는 리비전 둘을 둔 임시 폴더에서는 둘이라 빨개짐을 본다. 실패 문구는 까닭을 적고 멈추고 사용자에게 물으라고만 한다.
- `tools/run_checks.py`의 `CHECKS`에 `check-notes`, `ci.yml`의 `ticket` 잡에 노트 검사 스텝, `.github/workflows/pr-title.yml`(PR을 고쳤을 때 도는 작은 워크플로, `verify`에 들지 않는다)을 더했다. PR 제목은 환경 변수 `PR_TITLE`로만 넘기고 시험이 제목 식이 든 줄을 모두 본다.
- `.github/PULL_REQUEST_TEMPLATE.md`에 "업그레이드할 때 운영자가 손댈 것" 칸(마이그레이션, 재색인, 계약 앞자리)을 더하고 `.env.example` 줄이 `deploy/standalone/.env.example`을 가리키게 고쳤다. 원고 폴더 셋은 미리 만들지 않았다.
- `tests/tools/test_check_notes.py`(새 파일): agent-os 시험 사례 79개 가운데 78개를 같은 이름으로 옮기고(나머지 하나는 제품 경로가 다섯에서 넷이라 이름의 수를 고쳤다) 마이그레이션 사례와 배선 시험을 더했다.
- `.scratch/release-image/probes/check_notes_mutations.toml`: 변이 열네 개(열셋은 구현 때, 하나는 PR 직전 리뷰를 반영하며 더했다).
- `tools/release.py` 독스트링, `.claude/skills/next-session/merge.md`, `docs/agents/issue-tracker.md`의 05가 들인다는 미래형 문장을 현재형으로 고쳤다.

## 확인한 것

- 변이 열세 개가 모두 기대대로 빨개졌다(열네째는 아래 PR 직전 리뷰에서 더했고 역시 기대대로다). 첫 판에서 변이 하나(harness 폴더를 기능으로 센다)가 살아남아 그 갈래를 고정하는 시험을 더했다. 표지는 처음에 시험 원문에 글자 그대로 있는 문구로 적어 `--check`가 거절했다(시험 원문의 메시지는 실패 출력의 코드 조각에 늘 실려 표지가 되지 못한다). 단언 메시지에 실제 값을 끼워 만들고 값과 뒤 글이 이어진 부분을 표지로 골랐다.
- `uv run ruff check .`와 `uv run ruff format --check .`가 초록이다. `uv run python tools/run_checks.py`는 `check-notes`, `check-ticket`, `zizmor`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`가 통과했고 pytest는 4835개가 지나고 `tests/adapters/test_postgres_engine.py`의 연결 상한 시험 하나가 10초 제한에 걸려 빨갰다. 이 실행은 19분이 걸린 부하였고 테스트 DB를 띄워 그 파일만 돌리면 통과했다. 이 변경이 닿는 곳이 아니다. 커밋이 부르는 pre-commit이 전체를 한 번 더 돌린다.
- `tools/sibling_overlap.py`는 번호 겹침이 없다고 했다(종료 0).
- 저장소의 squash 병합 제목 설정은 `COMMIT_OR_PR_TITLE`이다. 티켓의 지시대로 `PR_TITLE`이 아니라 병합 전에 사용자에게 알린다.

## 셀프 리뷰

`/code-review`의 표준 축(sonnet / high)과 명세 축을 나란히 돌렸다. 범위는 base `fa85261`, 파일 여덟(추적 변경)과 추적하지 않는 새 파일 다섯, 커밋 0이다. 두 축 모두 Critical과 Major가 없었다.

- 고쳤다(Nit, 명세 축): `ci.yml`의 노트 검사 스텝에 `if: ${{ !cancelled() }}`가 없어 앞 스텝(`check_ticket`)이 빨가면 노트 검사가 돌지 않았다. agent-os의 같은 스텝은 앞 스텝이 빨강이어도 돈다. 조건과 주석을 더했다.
- 고쳤다(Nit, 명세 축): 시험 함수 이름 다섯과 주석 둘에 옛 말(조각, 판 내기)이 남았다. 원고와 릴리스를 내는 도구로 고쳤다. 마이그레이션 변이 표가 가리키는 시험은 이름이 바뀌지 않았다.
- 고쳤다(Minor, 표준 축): `Last Amended`가 판을 올린 날(오늘)이 아닌 어제 날짜였다. 2026-11-20으로 고쳤다.
- 고쳤다(Minor, 표준 축): `_NOTES_PATHS`가 `tools.release.NOTES_ROOT`와 같은 글자를 따로 적었다. 가져다 쓴다.
- 고쳤다(Nit, 표준 축): 제목을 고쳤을 때만 도는 워크플로라는 서술이 부정확했다. `edited`는 본문을 고쳐도 돈다. 독스트링과 워크플로 머리 주석을 고쳤고 시험 이름은 티켓의 말을 따라 두었다.
- 고쳤다(Nit, 표준 축): 티켓 Comments가 400자 문턱을 agent-os가 잰 값이라 적었으나 원본은 정한 값이다. 고쳤다.
- 남긴다(Nit, 명세 축): `versions/__init__.py`나 `versions/__pycache__/x.py` 같은 리비전이 아닌 `.py`도 마이그레이션으로 센다. 티켓은 `versions/` 아래의 `.py`라고 적었고 독스트링이 경로만 본다고 밝힌다.
- 남긴다(Minor, 표준 축): 독스트링의 못 보는 것 두 항목(얕은 클론의 (나), `--no-verify`나 `SKIP`으로 지나가는 커밋 검사)을 시험이 고정하지 않는다. `.claude/rules/tools.md`는 새로 적거나 고치는 항목마다 시험을 요구하지만, 둘은 agent-os에서 옮긴 항목이고 이 규칙은 앞서 적은 항목을 소급하지 않는다.
- 남긴다(Nit, 표준 축): `Scene.before: str | None`, 필드 하나뿐인 `Wording`, 약 50줄의 `feature_problems`는 원본에서 온 모양이다.
- 남긴다(범위 밖): `docs/constitution/operations.md`의 07이 더한다는 문장은 사용자의 승인 범위 밖이라 사용자에게 알린다.

고치며 새로 쓴 사실 문장(PR 직전 리뷰가 밀 주장):

1. `ci.yml`의 주석: 앞 스텝이 빨강이어도 돌아 두 결과를 함께 본다.
2. `tools/check_notes.py` 독스트링과 `pr-title.yml` 머리 주석: PR을 고쳤을 때(`edited`, 제목뿐 아니라 본문을 고쳐도 돈다) 도는 워크플로.
3. `docs/constitution/README.md`: 판 1.5.4, `Last Amended` 2026-11-20.

다시 돌린 명령: `uv run pytest tests/tools/test_check_notes.py tests/adapters/test_migration_heads.py tests/tools/test_release.py`가 통과했고 `ruff`와 `pyright`가 초록이다. 전체 러너는 아래 "커밋"의 pre-commit이 돈다.


## PR 직전 리뷰

`coderabbit-review` 서브에이전트가 CodeRabbit CLI 0.7.5로 스테이지된 변경 전부를 리뷰했다(`--base fa85261e10a0ce3138d4570194e1d83090a31ded`, 좌석은 `Seat: not assigned`, 플랜은 Free였지만 끝까지 돌았다). 결과는 8건이고 Major가 둘, Minor가 여섯이다. 서브에이전트가 밀 주장을 재서 알린 것이다. `ci.yml`의 `!cancelled()` 조건과 env 전달, `edited` 이벤트가 제목·본문·base 변경에 모두 발동한다는 점(GitHub 문서), `NOTES_ROOT` 가져다 쓰기, 헌법 판과 `Last Amended`의 일관이 참이었다. 마이그레이션 판정의 경계 입력은 코드를 읽어서만 확인했다(임시 저장소를 만드는 명령을 워크트리 가드가 거절했다). 비밀이나 질문 내용을 남기게 하는 문장은 없었다. 지적은 CLI 출력을 데이터로만 다루고 현재 코드와 대조해 판정했다.

- 고쳤다(Minor): 시험이 워크플로 전체 글에서 `PR_TITLE:`을 찾아, 제목을 받는 env를 다른 스텝으로 옮겨도 통과했다. 노트 검사를 부르는 스텝 자신의 env가 `PR_TITLE`을 받는지 보게 좁히고, 그 갈래를 변이 14(검사 스텝의 env 키 이름을 바꾼다)로 고정했다. `pr-title.yml`의 매개변수는 머리 주석에도 있는 `--title-only`가 아니라 실행 명령 전체로 바꿨다.
- 고쳤다(Nit, 서브에이전트 보고): `docs/agents/issue-tracker.md`의 05가 들인다는 문장이 이 변경으로 낡아 현재형으로 고쳤다. 같은 낱말을 `docs`, `tools`, `.claude`에서 다시 찾아 살아 있는 문서의 잔존은 0이다(일지는 옛 말을 인용하는 기록이라 센 것에서 뺀다).
- 남긴다(Major로 분류됨): 머리 브랜치 이름이 `main`이나 `dev`면 건너뛰는 면제가 포크에서 온 PR에도 열린다. 포크의 기본 브랜치도 `main`이다. 면제 기준이 머리 브랜치 이름인 것은 명세 "번호와 느낌표"가 정한 것이고, 이 저장소는 혼자 쓰는 저장소라 포크 PR이 없다. 필수 검사 `verify`는 그대로 돈다. 팀원이 생겨 포크 PR이 열리면 같은 저장소의 머리만 면제하도록 조일지 그때 ADR로 정한다. 티켓 Comments에 적었다.
- 남긴다(Major로 분류됨): dev가 fetch 이후 바뀌어도 이전 판정을 재사용한다는 지적은 맞지 않다. 판정은 PR의 base와 머리의 merge-base에서 머리까지의 변경을 보므로 dev가 움직여도 PR 자신의 변경은 같다. 병합 직전 확인은 병합 절차(`merge.md`)가 맡는다.
- 남긴다(Minor 다섯): 얕은 클론에서 merge-base가 찾아지면 (나)가 이력을 덜 본다는 것은 독스트링의 못 보는 것에 이미 적혔고 워크플로가 `fetch-depth: 0`으로 받는다. 나머지 넷(스테이지 목록과 본문이 서로 다른 색인 상태를 볼 수 있다는 지적, `git show` 실패를 부재로 읽는 `_read`, `git log --name-only`의 이름 바꾸기 감지, 줄 단위로 읽는 경로)은 agent-os 원본의 모양이다. 이 티켓은 원본의 이식이라 고치지 않았고, 실제로 틀리는 입력은 재현하지 못했다. 코드를 읽어 판정했을 뿐 입력을 만들어 돌려 보지는 않았다.

고치며 새로 쓴 사실 문장(병합 전 마지막 리뷰가 밀 주장):

1. 이 절이 `edited` 이벤트가 제목, 본문, base 변경에 모두 발동한다고 적은 문장.
2. 변이 14가 `ci.yml`의 `PR_TITLE:` 줄 하나(그 파일에 하나뿐이다)의 키만 바꿔 검사 스텝의 env 갈래를 고정한다는 것.
3. `docs/agents/issue-tracker.md`의 노트 검사를 `tools/check_notes.py`로 가리키는 문장.

## 커밋

첫 커밋은 `d768260`(15개 파일, 2031줄 더함, 19줄 뺌)이다. 커밋 전 `git branch --show-current`는 `feature/05-notes-check-guards-upgrade-bang`이었고 `git fetch origin` 뒤 `origin/dev`는 기준 `fa85261`과 같았다. 커밋이 부른 pre-commit이 새 항목을 실제로 돌렸다. `check-notes`가 0.8초에 통과했고 `ruff check`, `ruff format`, 검사 러너 열한 가지(`parallel-checks` 494.11초, 그 안의 pytest 493.8초), 표, 줄 구분 문자, 변이 표, 헌법 판, 인용 대조, 커밋 메시지 훅이 모두 통과했다. 앞서 손으로 돌린 전체 러너에서 한 번 빨갛던 연결 상한 시험(`tests/adapters/test_postgres_engine.py`)도 이번에는 통과했다. 인용 대조가 막지 않는 경고 둘을 냈다. 티켓 Comments와 이 일지가 이미 없는 옛 문장이나 요약 문장을 따옴표로 옮긴 곳이다. 따옴표를 떼고 풀어 써서 둘째 커밋에서 고쳤다.

## 회고

후보는 아홉이다. 승인 1, 기각 8(그 가운데 일지에만 남기는 것 1), 넘김 0이다. 만료할 항목은 없었다(`uv run python tools/queue_open_rows.py`를 두 번, 두 번째는 `git fetch origin` 뒤 `--ref origin/dev`로 쳤고 둘 다 "(없음)"이었다).

승인:

- `decision-word-residue`의 7회차. 사건: 05가 노트 검사를 들인다는 미래형 문장을 `tools/release.py`와 `merge.md`에서 고쳤지만, `docs/agents/issue-tracker.md`의 같은 뜻의 문장은 찾지 못했고 PR 직전 `coderabbit-review`가 잡았다. 작업 규약 4(옛 표현을 grep해 잔존 0)를 어긴 사건이라 회차로 센다. 열린 항목이 이미 처방했으므로(다섯 번째면 계기 훅 후보) 새 항목을 쓰지 않고 그 항목의 승인 줄에 회차와 이 일지 파일명을 더했다. 항목의 회차는 6에서 7이 되었다. 이 일지에는 앞서 적은 회차가 없어 중복으로 더하지 않았다.

일지에만 남긴다:

- 연결 상한 시험(`tests/adapters/test_postgres_engine.py`)이 전체 러너를 손으로 돌릴 때 한 번 빨갰고 혼자 돌리면 초록이었으며 커밋의 pre-commit에서는 두 번 초록이었다. 부하에 민감한 시간 시험의 종류는 사용자가 2026-11-15에 닫힌 채로 두기로 한 것이라 새 사례는 일지에만 적고 항목을 잇지 않는다.

기각(조건: 이미 있는 검사, 훅, 앱 가드가 그 자리에서 막거나 알렸거나, 이 세션에 사건이 없다):

- `mutate.py --check`가 시험 파일에 글자 그대로 들어 있는 기대 출력 표지를 거절했다. 검사가 그 자리에서 알렸고 단언 메시지에 실행 시점의 값을 넣는 쪽으로 고쳤다.
- 워크트리 가드가 이어 붙인 git 명령을 거절했고, 40줄이 넘는 heredoc을 훅이 막았고, `.env`에 닿는 Grep 글롭을 훅이 막았다. 셋 모두 가드가 그 자리에서 막았다.
- 인용 대조가 낸 경고 둘과 E501 알림. 검사가 그 자리에서 알렸다.
- 헌법 판 `Last Amended`와 버전의 일관. 이 세션에는 어긋난 사건이 없었고 PR 직전 리뷰가 일관을 확인했다.
- `coderabbit-review` 서브에이전트가 CLI 리뷰가 끝나기 전에 한 번 보고를 넘겼다. 앱이 둘째 넘김을 거절했고 본 세션이 산출 파일을 직접 읽어 8건을 모두 얻었으며 잃은 결과가 없다. 원인이 CLI의 지연인지 정의의 문제인지 이 세션에서 가려지지 않았다.

## 다음

이 PR(base dev)은 헌법 판 1.5.4(문구 수정)를 올린다. 병합 전에 풀 일이 하나 있다. 티켓의 수락 기준이 병합 전에 보라고 한 저장소 설정 `squash_merge_commit_title`이 `COMMIT_OR_PR_TITLE`이고 `PR_TITLE`이 아니다. 설정이 `PR_TITLE`이 아니면 검사를 지난 PR 제목이 아니라 커밋 제목이 dev에 남을 수 있으므로 병합하지 않고 사용자에게 알린다. 이 PR은 커밋이 둘이라 `COMMIT_OR_PR_TITLE`에서는 PR 제목이 쓰이지만, 티켓의 지시가 `PR_TITLE`이 아니면 알리고 기다리라는 것이라 그대로 따른다.

- 사용자 결정 하나: `docs/constitution/operations.md`의 07이 `claude-code-review.yml`에 더한다는 문장이 07의 병합(PR #75)으로 낡았다. 이 승인 범위 밖이라 두었다. 고치려면 한 낱말(더한다를 더했다로)이고 헌법 문서라 사용자 승인이 필요하다.
- 08 이후: `tools/release.py` 29줄 근처의 08이 들인다는 문장은 08이 닫힐 때 걷는다.
- 포크 PR이 열리게 되면 머리 브랜치 이름으로 하는 면제를 같은 저장소의 머리로 조일지 ADR로 정한다.
- 이 PR의 CI에서 `ticket` 잡이 노트 검사를 돌아 지난 실행의 주소는 티켓 Comments에 적었다(머리 `3aa88ae`). 이 뒤의 커밋에서도 `ticket` 잡은 다시 돈다.
- release-image의 프런티어: 05가 닫히면 03(단독 compose)이 이미 열려 있고 04는 03 뒤, 08은 01부터 07까지가 모두 닫힌 뒤다. 세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
