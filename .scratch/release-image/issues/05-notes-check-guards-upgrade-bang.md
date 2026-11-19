# 05: 노트 검사와 PR 제목 검사가 느낌표와 업그레이드 원고의 짝을 병합 전에 막는다

**What to build:** 개발 세션이 PR 제목에 느낌표(`feat!:` 꼴. 업그레이드할 때 운영자가 손댈 것이 있다는 표시)를 붙였는데 업그레이드할 때 할 일의 원고(`docs/release-notes/upgrade/<이름>.md`)를 더하지 않았거나, 마이그레이션 파일을 고친 PR의 제목에 느낌표가 없으면 CI가 빨갛다(스토리 47, 48). 기능의 마지막 티켓이 그 기능을 소개하는 단락(`docs/release-notes/features/<slug>.md`)을 빠뜨리면 커밋이 막힌다(스토리 49). 출시 PR과 운영에서 개발로 합치기 PR은 이 검사에서 면제된다(스토리 50). PR 서식은 "업그레이드할 때 운영자가 손댈 것"을 세 항목으로 묻는다. 마이그레이션 리비전의 끝(alembic의 head)이 둘이 되면 저장소 상태 시험이 빨갛다.

agent-os 커밋 `1aac0cf`의 `tools/check_notes.py`와 그 시험, `.github/workflows/pr-title.yml`을 옮겨 이 저장소의 값으로 고치고, 마이그레이션 판정 하나를 더한다. 노트 검사는 02의 도구에서 제품 변경의 경로 목록과 제목 읽기를 가져다 쓴다.

근거는 명세 "번호와 느낌표"의 마이그레이션 파일·판정의 자리·PR 서식의 칸·면제·head가 하나인지 보는 시험·원고의 짝·squash 제목 항목, "릴리스 노트"의 원고 폴더의 꼴과 기능 단락 판정, "PR 서식, 노트 검사, 검사 러너" 전부, "배포 파일 묶음"의 PR 서식 `.env.example` 줄 항목, Testing Decisions의 도구 시험 항목(노트 검사와 더하는 경우 셋 가운데 마이그레이션 판정)이다.

**Blocked by:** 02 (제품 변경의 경로 목록과 제목 읽기), 06 (운영 문서의 느낌표 기준과 막는 글이 가리킬 절 이름. 헌법을 바꾸는 06이 첫 티켓이다)

**Status:** done

- [x] 시작할 때 agent-os의 변경을 본다. `git -C C:/project/agent fetch origin` 뒤에 `git -C C:/project/agent log b74a8adf2..origin/dev -- .github/workflows/release.yml tools/release.py tools/release_ci.py tools/check_notes.py deploy/ tests/tools/test_release.py tests/tools/test_release_ci.py tests/tools/test_release_workflow.py tests/tools/test_check_notes.py tests/tools/test_deploy_guide.py`가 비지 않으면, 또는 같은 범위에서 `.github/workflows/pr-title.yml`이나 `.github/PULL_REQUEST_TEMPLATE.md`가 바뀌었으면 그 변경을 함께 옮길지 사용자에게 묻고 멈춘다(명세 "따르는 것과 옮기는 방식"). 두 명령 가운데 하나라도 오류로 끝나면 빈 출력으로 보지 않고 그 오류를 보고하고 멈춘다. 바뀐 파일이 이 티켓이 옮기는 파일이 아니면 묻지 않고 그 커밋을 Comments에 적고 잇는다. 사용자에게 물었으면 그 답과 본 agent-os 커밋을 Comments에 적는다. 기점이 `1aac0cf`가 아니라 `b74a8adf2`인 까닭은 명세 "따르는 것과 옮기는 방식"이 적는다.
- [x] 노트 검사는 agent-os의 판정 셋을 옮긴다. (가) 제목과 느낌표와 업그레이드 원고의 짝(CI만), (나) 기능 단락의 빠뜨림, (다) 원고의 꼴이다. 기능이 아닌 폴더는 `harness`와 `retro-queue`다. 커밋 전 검사 러너(`tools/run_checks.py`의 `CHECKS`)의 항목, `ci.yml`의 `ticket` 잡의 스텝, 제목을 고칠 때만 도는 PR 제목 워크플로(필수 검사가 아니다)에서 돈다. 제목은 워크플로 식에 바로 넣지 않고 환경 변수로 넘긴다(PR 제목 같은 바깥 입력을 워크플로 식에 바로 넣으면 그 안에 든 명령이 실행될 수 있다. 워크플로의 보안 약점을 찾는 감사 도구 zizmor가 template-injection으로 막는 꼴이다).
- [x] (가)에 마이그레이션 판정을 더한다. `src/rag_engine/adapters/postgres/migrations/versions/` 아래의 `.py` 파일을 더하거나 고치거나 지우거나 옮긴 PR의 제목에 느낌표가 없으면 막는다. 옮긴 파일은 옛 경로와 새 경로를 모두 본다. 티켓 PR과 핫픽스 PR에 걸고, 머리가 dev인 출시 PR과 머리가 main인 운영에서 개발로 합치기 PR은 면제한다(명세 "번호와 느낌표").
- [x] 마이그레이션 리비전의 head가 하나인지 보는 저장소 상태 시험을 둔다. 시험은 이 저장소의 마이그레이션 폴더에서 head를 세고, 같은 부모를 가리키는 리비전 둘을 둔 임시 폴더에서는 head가 둘이라 빨개지는 것도 본다. 실패 문구는 할 일을 짐작해 시키지 않는다. 두 head가 생긴 까닭(핫픽스와 dev의 마이그레이션이 같은 부모를 가리킨다)을 적고, 멈추고 사용자에게 물으라고 적는다. 운영에서 개발로 합치기 PR은 머리가 main이라 그 PR에 합치는 리비전을 더할 자리가 없다(명세 "번호와 느낌표"의 head 항목).
- [x] 실패하는 시험을 먼저 쓴다. agent-os의 사례를 모두 옮기고, 마이그레이션 판정의 사례(더함, 고침, 지움, 옮김, 느낌표가 있으면 지남, 출시 PR과 운영에서 개발로 합치기 PR의 면제)를 더한다. 임시 git 저장소에서 돈다(선례 `tests/tools/test_check_ticket.py`).
- [x] PR 서식(`.github/PULL_REQUEST_TEMPLATE.md`)에 칸 "업그레이드할 때 운영자가 손댈 것"을 더하고, 마이그레이션, 재색인이 필요해지는 변경(색인 판의 요소가 바뀌는 것, ADR 0008), 계약의 판에서 앞자리를 올리는 변경의 세 항목을 따로 묻는다. 하나라도 있으면 제목에 느낌표를 붙이고 `upgrade/` 원고를 싣는다는 안내를 함께 둔다. 마이그레이션 PR의 원고는 업그레이드 전에 PostgreSQL 볼륨을 백업하라는 한 줄로 쓴다고 적는다(백업과 복원의 절차는 backup-upgrade가 정한다). 서식의 "새 환경 변수는 `.env.example`에 있다" 줄은 `deploy/standalone/.env.example`을 가리키게 고친다(03이 만드는 파일이다. 03보다 먼저 병합되면 그동안 서식이 아직 없는 파일을 가리키는데, 지금도 그 줄이 가리키는 파일은 없다).
- [x] 원고 폴더 셋(`features/`, `upgrade/`, `intro/`)은 agent-os처럼 빈 폴더를 미리 두지 않는다. 첫 원고가 들 때 생긴다. 노트 검사와 02의 도구는 폴더가 없을 때도 돈다.
- [x] 검사의 막는 글과 독스트링은 이 저장소의 이름(업그레이드할 때 할 일, 릴리스 노트 원고 등)으로 쓴다. 막는 글이 운영 문서의 절을 가리키면 06이 Comments에 적은 절 이름을 그대로 쓴다(06이 먼저 병합된다).
- [ ] 병합하기 전에 사람 몫(세션이 대신할 수 없어 사용자가 직접 하는 준비) 하나가 끝났는지 본다. squash 병합의 제목을 PR 제목으로 쓰는 저장소 설정이다(명세 "사람 몫"). `gh api repos/njh6803/rag-engine --jq .squash_merge_commit_title`이 `PR_TITLE`이 아니면 사용자에게 알리고 기다린다. 바뀌기 전에 병합하면, 검사를 지난 PR 제목이 아니라 커밋 제목이 main에 남을 수 있다.
- [ ] 이 티켓은 PR 서식과 `ci.yml`과 커밋 전 검사 러너를 고치는 하네스 일이기도 하다. 고친 뒤 커밋 전 검사가 새 항목을 실제로 도는지 한 번 커밋해 보고(작업 규약 3), 이 PR의 CI에서 `ticket` 잡이 노트 검사를 돌아 지난 것을 실행의 주소로 Comments에 적는다.
- [x] 검사 넷이 초록이다.

## Comments

### 2026-11-20 구현 세션이 남긴 확인

- **agent-os 변경 확인.** `git -C C:/project/agent fetch origin`이 종료 0으로 끝났고, 이어 `git -C C:/project/agent log b74a8adf2..origin/dev -- <티켓이 적은 경로 열 개>`도 종료 0에 출력이 비었다. 옮길 변경이 없어 사용자에게 묻지 않았다. 옮긴 원본은 agent-os `1aac0cf`의 `tools/check_notes.py`와 그 시험이다.
- **옮긴 것.** 판정 셋 (가)(나)(다)와 세 모드(인자 없음은 (나)(다), `--ci`는 셋 모두, `--title-only`는 (가)만)를 옮겼다. 머리 브랜치가 `main`이나 `dev`면 건너뛰고(출시 PR과 운영에서 개발로 합치기 PR), 핫픽스 PR은 건너뛰지 않는다. 막는 글과 독스트링은 이 저장소의 이름으로 고쳤고 규약 원천은 운영 문서의 "릴리스 노트 원고"다(06이 Comments에 적은 이름). 독스트링의 400자 문턱은 agent-os가 정한 값을 옮긴 것이고 이 저장소에서 재지 않았다고 적었다.
- **더한 것.** (가)의 마이그레이션 판정이다. `src/rag_engine/adapters/postgres/migrations/versions/` 아래 `.py`를 더하거나 고치거나 지우거나 옮기면 제목에 느낌표가 있어야 한다. 하위 폴더도 센다. 이름 바꾸기는 `--no-renames`로 지움과 더함 둘로 보아 옛 경로와 새 경로를 모두 본다. 경로만 본다(내용을 읽지 않는다). 못 보는 것으로 재색인과 계약 앞자리 변경은 기계가 못 가린다고 독스트링에 적었다.
- **head 시험.** `tests/adapters/test_migration_heads.py`다. 이 저장소의 폴더에서 head가 하나임을 재고, 같은 부모를 가리키는 리비전 둘을 둔 임시 폴더에서는 head가 둘이라 빨개짐을 본다. 실패 문구는 까닭(핫픽스와 dev의 마이그레이션이 같은 부모를 가리킨다)을 적고 "멈추고 사용자에게 묻는다"고만 하며 할 일을 시키지 않는다. 시험이 지난 문구를 단언한다. 폴더가 비면 "하나도 없다"로 빨개진다.
- **배선.** `tools/run_checks.py`의 `CHECKS`에 `check-notes`, `ci.yml`의 `ticket` 잡에 두 번째 스텝, 새 `.github/workflows/pr-title.yml`(제목을 고칠 때만 돌고 `verify`에 들지 않는다)이다. 제목은 두 곳 모두 `PR_TITLE` 환경 변수로만 넘기고, 시험이 워크플로 글에서 제목 식이 든 줄이 모두 `PR_TITLE:`로 시작함을 본다. `zizmor`가 초록이다. 명령 앞에서 `::stop-commands::`로 워크플로 명령을 멈춘다(출력에 PR이 고른 이름이 실리기 때문이다).
- **PR 서식.** "업그레이드할 때 운영자가 손댈 것" 칸에 세 항목(마이그레이션, 재색인, 계약 앞자리)과 느낌표·`upgrade/` 원고 안내를 더했고, `.env.example` 줄은 `deploy/standalone/.env.example`을 가리킨다.
- **폴더.** `features/`, `upgrade/`, `intro/`는 만들지 않았다. 폴더가 하나도 없는 임시 저장소에서 세 모드가 모두 돈다는 시험이 있다.
- **변이.** `.scratch/release-image/probes/check_notes_mutations.toml`의 열네 변이(PR 직전 리뷰를 반영하며 검사 스텝의 env를 보는 변이를 하나 더했다. 앞의 열세 변이는 마이그레이션 판정 넷, 이름 바꾸기, 400자 문턱, 있던 원고 고침, harness 폴더, 제목만 모드, 검사 러너 항목, `ci.yml` 호출, 제목 식, PR 제목 워크플로 트리거)가 모두 기대대로 빨개졌고 표지 점검(`--check`)도 통과했다. 첫 판에서 변이 8(harness를 기능으로 센다)이 살아남아 `test_기능이_아닌_폴더는_끝_줄과_제품_변경이_함께여도_단락을_묻지_않는다`를 더했다.
- **검사 러너.** `uv run ruff check .`, `uv run ruff format --check .`, `uv run python tools/run_checks.py`의 `check-notes`, `check-ticket`, `zizmor`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`가 초록이다. pytest는 4835개가 지나고 `tests/adapters/test_postgres_engine.py`의 연결 상한 시험 하나가 10초 제한에 걸려 한 번 빨갰다(8개 작업자로 19분이 걸린 부하였다). 테스트 DB를 띄워 그 파일만 따로 돌리면 초록이었다. 이 변경이 닿는 곳이 아니다.
- **헌법.** 사용자가 승인해 `docs/constitution/operations.md`에서 "release-image의 05가 들인다. 들어오기 전에는 … 장치는 아직 없다" 문장을 걷고 헌법 버전을 1.5.3에서 1.5.4(문구 patch)로 올렸다. 같은 문서의 "release-image의 07이 `claude-code-review.yml`에 더한다" 문장은 07이 병합돼 낡았지만 승인받은 범위 밖이라 두었다.
- **squash 설정(병합 전 확인).** `gh api repos/njh6803/rag-engine --jq .squash_merge_commit_title`이 `COMMIT_OR_PR_TITLE`을 냈다(`PR_TITLE`이 아니다). 이 티켓의 지시대로 사용자에게 알리고, 설정이 바뀌기 전에는 병합하지 않는다.
- **면제와 포크.** 머리 브랜치가 `main`이나 `dev`면 건너뛰는 면제는 포크에서 온 PR에도 열린다(포크의 기본 브랜치가 `main`이다). 기준이 머리 브랜치 이름인 것은 명세가 정했고 지금은 혼자 쓰는 저장소라 포크 PR이 없다. 팀원이 생겨 포크 PR이 열리면 같은 저장소의 머리만 면제하도록 조일지 ADR로 정한다. CodeRabbit CLI가 Major로 냈다.
- **옛 말 잔존.** `docs/agents/issue-tracker.md`의 05가 들인다는 문장을 현재형으로 고쳤다. `docs/constitution/operations.md`의 07이 더한다는 문장은 승인 범위 밖이라 남아 있다. 사용자가 고치라고 하면 한 단어(더한다를 더했다로)다.
