"""병합된 워크트리와 로컬 브랜치를 판정하고, 후보 하나씩 지운다. `tidy-checkouts` 스킬 3이 부른다.

세션마다 판정과 삭제 스크립트를 스크래치에 새로 짓다가, 사용자가 끊은 호출이 지우는 도중에 죽어
지우다 만 폴더가 생겼다(대기열 132, 일지 2026-10-07-02). 그래서 판정은 이 도구가 한 번에 내고,
삭제는 후보 하나마다 따로 부른다. 끊긴 호출이 망가뜨리는 것은 많아야 하나다.

사용(주 체크아웃에서):
    uv run python tools/tidy_checkouts.py judge [--running "<제목이나 브랜치>" ...]
                                                [--idle <세션 id> ...]
    uv run python tools/tidy_checkouts.py remove "<경로>" <브랜치|.detached> <HEAD>
    uv run python tools/tidy_checkouts.py remove-branch <브랜치> <커밋>
    uv run python tools/tidy_checkouts.py remove-stray "<경로>"
    uv run python tools/tidy_checkouts.py restore "<경로>.tidy-probe"
    uv run python tools/tidy_checkouts.py end-holders "<경로>" <세션 id> [<세션 id> ...]
    uv run python tools/tidy_checkouts.py empty-trash

`--running` 은 `list_sessions` 에서 이 세션을 뺀 `isRunning` 세션의 제목과 브랜치(`branch`)다.
앱이 적은 브랜치는 세션을 만들 때의 이름이라, 세션 안에서 브랜치를 바꾸면 체크아웃된 브랜치와
다르다(2026-10-20 에 실행 중 세션의 `claude/hungry-robinson-5cb964` 를 제목만 받은 판이 지울
후보로 냈다). `--idle` 은 프로세스를 끝내도 되는 쉬는 세션의 id(`sessionId`)다. 고르는 기준은
부르는 쪽(스킬)이 정한다. 도구는 앱의 세션을 보지 못해 부르는 쪽이 넘긴다. 이 도구를 부른 세션
(환경의 `SESSION_ENV`)은 `--idle` 에 있어도 뺀다. `judge` 는 줄마다 `지운다`·`남긴다`·
`넘긴다`(사람에게)·`되돌린다`·`끝낸다`와 이유를 찍고, 지울 것에는 부를 `remove`·`remove-branch`·
`remove-stray` 명령을, 되돌릴 것에는 `restore` 를, 끝낼 것에는 `end-holders` 를 붙인다. 끝에
휴지통(`TRASH_DIR`)에 남은 것이 있으면 항목마다 쥔 프로세스와 함께 찍고 `empty-trash` 를 붙인다.
경로나 브랜치 이름에 셸이 풀 수 있는 글자가 들었으면 명령 없이 넘긴다. git 은 모두
`core.longpaths=true` 로 친다(스킬 머리 문단).

판정. 워크트리마다 아래 순서로 보고 처음 어긋난 것을 이유로 찍는다. 모두 맞아야 지운다.
- 자리. 폴더가 없으면(등록이 `prunable` 이든 아니든) 잃을 것이 없어 지운다. `remove` 가 등록만
  걷는다(git 2.32 의 `worktree remove` 는 폴더가 없으면 종료 0으로 등록을 걷는다. 임시 저장소에서
  손으로 봤다, 일지 2026-10-15-06). 다만 옆 이름(`.tidy-probe`)에 폴더가 남아 있으면 되돌릴 일이라
  넘기고, 그 옆 이름 폴더에 `restore` 를 찍는다. 등록이 `prunable` 인데 폴더가 있으면 `.git` 이
  있을 때는 넘기고, 없을 때는 지우다 만 폴더라 아래 "등록 없는 폴더"의 판정으로 내용을 가른다
  (`_judge_all`). git 은 폴더가 있는 채로는 그 등록을 걷지 않아(`validation failed`, 손으로 봤다),
  `remove` 가 폴더를 휴지통으로 옮긴 뒤 등록을 걷는다. 그 폴더에서 친 git 은 루트 저장소에 닿아
  status 를 쓸 수 없다(대기열 135, 일지 2026-10-07-03). 폴더가 있는데 `git rev-parse
  --show-toplevel` 이 그 경로가 아니면 사람에게 넘긴다.
- 앱의 표지. 그 워크트리의 git 디렉터리(`git rev-parse --absolute-git-dir`, `.git/worktrees/
  <이름>/`)에 `APP_MARKER` 가 있으면 앱의 정리(`[WorktreePool]`)에 맡겨 남긴다(ADR 0032). 앱은 그
  워크트리를 새 세션에 다시 내준다. 2026-10-20 에 앱이 만든 분리 HEAD 워크트리 둘이 판정 1에서
  사람에게 넘겨졌고, 그 정리 도중에 앱이 그중 하나를 새 세션에 내주어 브랜치가 바뀌었다.
- 판정 1, 병합됐다. 분리 HEAD 는 그 커밋이 `origin/main` 에서 닿을 때만 다음 판정으로 가고(잃는
  것이 없다. 2026-10-15 에 모델 스윕과 옛 세션의 분리 HEAD 일곱이 넘겨진 채 남아 있었다), 아니면
  넘긴다. 브랜치는 병합된 PR 중 머리 브랜치 이름이 같은 것의 `headRefOid` 가 브랜치 끝(그 워크트리의
  HEAD)과 같거나, 브랜치 끝이 그 머리 가운데 하나의 조상이어야 한다(`behind_merged`. 로컬에만
  있는 커밋이 없다). 2026-10-20 에 `chore/skill-check-and-retro-section` 의 로컬 끝이 PR #114 의
  머리보다 커밋 넷 뒤였는데 사람에게 넘겼다. 머리 커밋이 이 저장소에 없으면(원격 브랜치가 지워진
  뒤 받아 오지 않았다) 조상인지 알 수 없어 넘긴다. 이름이 같은 PR 이 없으면 남기고, 있는데 머리와
  다르고 조상도 아니면 넘긴다. 이름만 보면 포크의 같은 이름 브랜치를 잡으므로 머리를 견준다.
  squash 라 `git log` 로는 가르지 못하고, 체크아웃된 브랜치는 끝이 `origin/main` 의 조상인 것으로도
  판정하지 않는다. 막 따고 커밋하지 않은 브랜치도 조상이다(일지 2026-10-05-05). 병합된 PR 은 `gh
  pr list` 한 번에 최근 1000개를 읽는다. 그보다 오래된 것은 병합되지 않은 것으로 보여 남는다(안전한
  쪽).
- 판정 2, 깨끗하다. `status --porcelain --untracked-files=all` 의 stdout 과 stderr 가 모두 비어야
  한다. stderr 의 경고는 git 이 그 아래를 보지 못했다는 뜻이다. `status --ignored=matching` 의 `!!`
  항목은 다시 만들 수 있는 것(`RECREATABLE_*`, 루트와 같은 `.claude/settings.local.json`)뿐이어야
  한다. 기본(`traditional`)은 무시된 것만 든 미추적 폴더를 그 폴더로 접어 찍어, 다시 만들 수 있는
  자리(`web/apps/widget/public/fonts/`)가 그 위 폴더로 보였고 위젯을 띄운 병합된 워크트리 아홉이
  남았다(대기열 464, 일지 2026-10-26-01). `matching` 은 무시 패턴에 맞은 자리만 찍는다(git 2.32 의
  임시 저장소에서 두 모드를 손으로 봤고, 시험이 그 접힘을 표지로 고정한다). 그래서 안쪽
  `.gitignore` 로만 무시되는 폴더(`.grimp_cache/`)와 윈도의 정션은 그 안의 항목이 하나씩 찍히고,
  판정과 옮기기 전에 그 항목을 가장 바깥의 링크나 다시 만들 수 있는 폴더인 조상으로 접는다
  (`fold_ignored`). 링크는 제 이름으로 판정되고 옮기기는 링크만 옮긴다. 추적 파일이 든 자리는 옮기지
  않는다(`ls-files`). 옮기면 추적 파일이 빠져 `git worktree remove` 가 막히고, 그 뒤 휴지통을 비우며
  함께 옮긴 다시 만들 수 없는 것(`.env`)도 지운다(PR 봇 CodeRabbit. 고치기 전 판을 셀프 리뷰 표준
  축이 임시 저장소로 밟았다). 그래서 추적 파일이 든 폴더로는 접지 않고 그 안의 항목을 제 이름이나 더
  안쪽 조상으로 판정한다. 추적 폴더를 갈음한 링크가 있으면 그 안에 무시된 것이 있든 없든
  남긴다(`tracked_links`). 윈도의 git 은 그 정션을 따라가 안의 파일이 체크아웃한 바이트와 같으면
  바뀐 것으로 찍지 않고(셀프 리뷰 명세 축이 재현했다), 링크째로 옮기면 추적 파일이 빠지며, 옮길 것이
  없으면 `git worktree remove` 가 정션을 따라가 링크 바깥의 파일을 지운다(PR 직전 bug-perf-review 의
  대체 리뷰가 임시 저장소로 재현했다). 바이트가 다르면(`core.autocrlf` 의 줄 끝만 달라도) 바뀐
  파일로 남는다(그 대체 리뷰와 그 반영의 셀프 리뷰가 임시 저장소로 봤다). 링크인지와 옮길
  항목이 있는지는 `\\\\?\\` 경로로 묻는다. MAX_PATH 를 넘는 링크가 링크가 아닌 것으로 보여 링크
  바깥을 지웠고(그 셀프 리뷰가 재현했다), 다시 만들 수 있는 이름의 그런 링크는 없는 것으로 보여
  옮기기가 건너뛰어 같은 길로 지웠다(그 반영 커밋의 대체 bug-perf-review 가 임시 저장소로
  재현했다). 워크트리를 읽을 때마다(`gather`) `ls-files` 를 한 번 띄우고 그 추적 폴더마다 링크인지
  한 번씩 본다. 이 저장소(추적 폴더 375개)의 워크트리 하나에서 앞의 것은 0.02~0.1초, 뒤의 것은
  0.07~0.34초였다(그 셀프 리뷰 때 손으로 열 번 봤다).
  설정의 같음은 `settings_equivalent` 다. 바이트가 같거나, 워크트리 스킬 사본 훅이 루트에 적는
  `skillOverrides` 의 `.claude/worktrees/` 키와 서식만 다르다(대기열 274).
  `git worktree remove` 는 무시된 파일을 묻지 않고 지운다. `.env` 나 `traces/` 가 있으면 남긴다.
- 판정 3, 주인이 없다. 제목이나 브랜치가 그 브랜치인 실행 중 세션이 있으면 남긴다. 잠금 사유는
  `claude session <이름> (pid <N>)` 모양이고 그 pid 가 살아 있으면 남긴다. 다만 산 잠금 pid 는 그
  워크트리를 연 세션의 `claude.exe` 라, 쥔 프로세스에 함께 넣어(`with_lock`) 그 세션이 `--idle` 로
  받은 세션이면 아래처럼 `끝낸다`로 낸다. `EnterWorktree(name)` 으로 만든 워크트리는 그 세션의 pid
  로 잠기고 인계 단계(`git worktree unlock`) 전에는 풀리지 않을 수 있어, 넣지 않으면 병합하고 쉬는
  세션의 워크트리를 끝내지 못한다(셀프 리뷰 명세 축). 산 잠금 pid 의 환경에 세션 id 가 든 것은 재지
  않았고, 들지 않았으면 세션을 모르는 프로세스로 보아 끄지 않는다. 죽었으면 `remove`
  가 풀고 지운다. 사유가 다른 모양이면 넘긴다. 잠금이 없다고 주인이 없는 것은 아니다.
  `git worktree add` 로 판 워크트리와 `EnterWorktree(path)` 로 들어간 워크트리는 잠기지 않는다(일지
  2026-10-06-04). 잠금 다음에는 그 폴더나 그 아래를 작업 디렉터리로 쥔 프로세스를 보고, 있으면
  이름과 pid 를 들어 남긴다(대기열 186). 쉬는 세션은 `isRunning` 이 아니라 제목으로 잡히지 않는데,
  데스크톱 앱이 `--resume` 으로 띄운 그 세션의 `claude.exe` 가 워크트리 루트를 쥐고 있었다(판정 4의
  1의 근거). 쥔 프로세스마다 환경의 세션 id(`SESSION_ENV`, `process_session`)를 읽어 pid 옆에
  적는다. 쥔 프로세스가 모두 `--idle` 로 받은 세션의 것이면 남기지 않고 `끝낸다`로 내고
  `end-holders` 를 붙인다(아래 "쉬는 세션의 프로세스"). 하나라도 세션을 모르거나 받지 않은 세션의
  것이면 남긴다. 앱은 쉬는 세션의 `claude.exe` 를 보관하기 전까지 띄워 두어(2026-10-20 에 앱이 띄운
  `claude.exe` 가 80여 개였다), 병합되고 깨끗한 워크트리가 그 세션이 보관될 때까지 남았다.
  이 단계가 없던 판은 그 워크트리를 지운다(또는 아래처럼 넘긴다)로 내고 `remove` 의 점유 탐침에서야
  막혔다(일지 2026-10-12-14). 프로세스는 `judge` 한 번에 한 번 훑는다. 그 세션에서
  `lock_holder.py --folder` 가 프로세스 720개 중 539개의 작업 디렉터리를 0.11초 안에 읽었다. 볼 수
  없으면(윈도·리눅스 밖의 OS, 32비트 파이썬, 읽다 실패) 이 단계를 건너뛰고 판정 4의 점유 탐침에
  맡긴다.
  그 폴더 아래 파일을 모듈로 올린 프로세스(대기열 201)는 이 판정이 보지 않는다. 2026-10-15 까지는
  보고 남겼는데, uv 의 `.venv` 와 pnpm 의 `node_modules` 가 기본으로 모듈 파일 다수를 캐시에서
  하드링크로 채워(Claude 세션의 uv 는 `UV_LINK_MODE=copy` 로 복사다, 대기열 217) 다른 워크트리에서
  도는 pytest·pre-commit·esbuild 가 병합된 워크트리 55개를 한꺼번에 남겼고, 그 프로세스 일곱 중
  다섯은 판정이 끝난 몇 분 뒤 이미 끝나 있었다(남은 둘은 pre-commit 과 다른 워크트리 `.venv` 의
  pytest. `Get-CimInstance Win32_Process` 로 손으로 봤다, 일지 2026-10-15-06). 올린 모듈은 이름
  바꾸기를 막지 않으므로(`lock_holder.py` 의 G, `worktree_occupancy.py` 의 E. 지우기가 막히는 것은
  `module_holder.py` 의 G·E) 판정 4가 그 폴더를 휴지통으로 옮긴 뒤 지우고, 지우다 막힌 것은 휴지통에
  남긴다(판정 4의 4·7). 모듈 훑기(`scan_modules`. 매핑 이름
  `GetMappedFileNameW` 와 그 파일의 다른 하드링크 이름 `FindFirstFileNameW`, 프로세스 770여 개에
  0.90~1.22초)는 등록 없는 폴더와 휴지통의 쥔 프로세스를 대는 데만 쓴다. 윈도 밖은 보지 않는다. 그
  OS 는 적재한 파일도 지울 수 있는 것으로 알고 있다(어림).
  제목이 체크아웃된 어느 브랜치와도 맞지 않는 실행 중 세션이 있으면, 프로세스의 작업 디렉터리를 읽을
  수 없는 OS 에서만 지울 워크트리 후보를 모두 넘긴다(그 세션이 어느 워크트리에 있는지 알 수 없다,
  일지 2026-10-06-03). 읽을 수 있으면 넘기지 않는다. 2026-10-15 에 실행 중 세션 다섯(`EnterWorktree`
  로 들어간 것 포함)의 `claude.exe` 가 모두 그 워크트리를 작업 디렉터리로 쥐고 있어 위의 훑기가
  잡았다(일지 2026-10-15-06). 그 전에는 제목이 브랜치가 아닌 세션 하나가 돌면 후보 전부가 넘겨졌고,
  새 세션의 첫 턴은 답을 기다리지 않아 아무것도 지워지지 않았다. 등록 없는 폴더는 넘기지 않는다.
  사람이 그 세션이 후보에 없다고 답하면 부르는 쪽이 `remove` 를 부른다. `remove` 의 재판정은 세션을
  보지 않고, 쥔 프로세스는 옮기기 직전에만 다시 본다(판정 4의 2).
체크아웃되지 않은 로컬 브랜치는 판정 1을 보고, 병합된 PR 이 없어도 끝이 `origin/main` 에서 닿으면
지운다(잃는 것은 이름뿐이다. `EnterWorktree` 가 만들고 세션이 떠난 `worktree-*` 브랜치 53개가 PR
없이 남아 있었다, 일지 2026-10-15-06). 병합된 PR 머리의 조상인 끝도 워크트리처럼 지운다.
PR 없이 끝이 `origin/main` 에 있어도 그 브랜치의 reflog 마지막 기록이 `FRESH_SECONDS` 안이거나
앞날이면 막 딴 브랜치라 남긴다(`is_fresh`, 대기열 440). `judge` 는 워크트리 목록을 읽은 뒤에
브랜치 목록을 읽어, 나란히 연 형제 세션이 그사이에 딴 브랜치(`EnterWorktree` 뒤 워크트리 안의 `git
switch -c`·`git branch -m`, 등록보다 브랜치를 먼저 만드는 `git worktree add -b`)는 체크아웃된
브랜치인데 체크아웃되지 않은 것으로 보인다. 첫 세션의 정리가 형제 셋의 브랜치를 지울 후보로
냈다(일지 2026-10-23-13. 형제가 어느 길로 땄는지는 적혀 있지 않다). 이름 바꾸기도 기록을 남겨 막
딴 것으로 본다.
`remove-branch` 의 재판정도 본다. 병합된 PR 로 지우는 두 길은 보지 않아, 주 체크아웃에서 병합하고
main 으로 옮긴 직후의 정리가 그 브랜치를 바로 지운다. 지울 것이어도 판정 3의 제목과 브랜치는
본다. 제목이나 브랜치가 그 브랜치인 실행 중 세션이 있으면 남긴다(`judge_branch`, 대기열 286.
이것을 보지 않던 판이 실행 중인 세션 `chore/mutate-followups` 의 브랜치를 지울 후보로 냈다, 일지
2026-10-16-15). 제목과 견줄 때도,
체크아웃됐는지 워크트리 등록과 견줄 때도(`judge` 와 `remove-branch`) 대소문자를 가리지 않는다
(`same_branch`. 글자 그대로 견준 판은 윈도에서 대소문자가 바뀌어 찍힌 체크아웃된 브랜치를 지울
후보로 냈고 `remove-branch` 가 지웠다, 대기열 286 셀프 리뷰). 잠금과 쥔 프로세스는 워크트리의
것이라 보지 않고, `remove-branch` 의 재판정은 `remove` 처럼 세션을 보지 않는다(아래 못 보는 것).
`main`·`master` 는 지우지 않는다(루트가 다른 브랜치에 있을 때 체크아웃되지 않은 브랜치로
보인다). `.claude/worktrees/` 아래인데 등록이 없는 폴더는 아래 "등록 없는 폴더"로 가른다.

판정 4, 지운다(`remove`). 후보 하나를 다시 판정하고(세션과 쥔 프로세스는 빼고. 쥔 프로세스는
1의 탐침과 2의 다시 거르기가 본다) 브랜치(분리 HEAD 는 `.detached`)와 HEAD 가 인자와 같을 때만, 아래
순서로 지운다. 폴더가 없으면 등록만 걷고 끝난다(자리 판정).
1. 점유 탐침. 워크트리 폴더를 옆 이름으로 바꿨다가 되돌린다. 윈도에서 그 아래를 작업 디렉터리로
   쥔 프로세스나 그 안의 파일을 연 프로세스가 있으면 이름 바꾸기가 막힌다. 그대로 지우면 git 은
   `Permission denied`·`Invalid argument` 로 지우다 만 폴더를 남긴다(`.scratch/harness/probes/
   worktree_occupancy.py` 의 B·C). 막히면 아무것도 바꾸지 않고 멈추고, 그 폴더나 그 아래를 작업
   디렉터리로 쥔 프로세스의 이름과 pid 를 이유에 붙인다(대기열 177). 윈도는 프로세스마다 PEB 의
   작업 디렉터리를, 리눅스는 `/proc/<pid>/cwd` 를 읽는다. 2026-10-12 에 DELETE 권한으로 열리지
   않던(공유 위반) 워크트리 셋은 모두 `claude.exe` 가 그 루트를 작업 디렉터리로 쥐었다. Restart
   Manager 는 폴더를 받지 않고 작업 디렉터리를 보지 못한다. 그중 한 워크트리의 파일 4만여 개를
   5000개 덩이로 등록하면 209초였고 덩이 일부는 오류 29 로 실패했으며, 쥔 `claude.exe` 대신 다른
   프로세스를 댔다(여기까지 `.scratch/harness/probes/lock_holder.py`). 그 `claude.exe` 셋의 부모는
   데스크톱 앱이었고, 그 세션들은 `list_sessions` 에서 `isRunning` 이 아니었다(손으로 봤다,
   `Get-CimInstance Win32_Process` 와 `list_sessions`, 일지 2026-10-12-08).
   되돌리기가 막히면 `RESTORE_WAITS` 만큼 기다리며 다시 시도하고, 끝내 막히면 멈춘다(종료 3).
   2026-10-12 에 옮기기는 지났는데 되돌리기가 `WinError 5` 로 한 번 막혀 폴더가 옆 이름에 남고
   등록이 폴더를 잃었다(대기열 202, 일지 2026-10-12-28). 그 틈에 무엇이 폴더를 쥐었는지는 재지
   않았다.
2. 다시 거르기. 판정 1~3을 한 번 더 내고, 옮길 무시된 항목도 그때 읽는다. 판정 뒤에 생긴 `.env` 나
   새 파일을 옮기지 않게 한다. 이때는 프로세스를 한 번 훑어 작업 디렉터리로 쥔 프로세스도 본다.
   리눅스의 탐침은 작업 디렉터리를 보지 못해, `judge` 뒤에 들어온 주인은 여기서 잡는다(PR #184
   리뷰). 어긋나면 아무것도 바꾸지 않고 멈춘다.
3. 죽은 잠금을 푼다. 1·2가 막히면 잠금도 그대로 남도록 그 뒤다.
4. 옮기기. 2가 읽은 무시된 항목을 휴지통(`TRASH_DIR` 아래 `<워크트리 이름>~~<상대 경로>`. 경로의
   `%` 는 `%25`, `/` 는 `%2F` 로 바꾸고, 겹치면 `~<번호>` 를 붙인다. `trash_slot`·`origin_of`)으로
   이름 바꾸기 한다. 휴지통 자리가 링크거나 폴더가 아니면 옮기지 않고 멈춘다(종료 1). 2026-10-15
   까지는 제자리에서 지웠는데(앞지우기), 다른 체크아웃의 프로세스가 하드링크 이름으로 올린
   `.pyd`·`.node` 하나에서 `WinError 5` 로 막혀 워크트리가 남았다(2026-10-07 에
   `mutate-restore-guard` 가 `yaml` 의 `.pyd` 에서, 일지 2026-10-07-15). 올린 모듈은 그 파일이 든
   폴더의 이름 바꾸기를 막지 않으므로(프로브의 E·G) 옮기기는 지나고, git 은 무시된 항목이 없는
   워크트리를 지운다. 옮기다 막히면 멈추고(종료 1), 먼저 옮긴 것은 휴지통에서 지운다. 등록과 `.git`
   파일은 남는다. 이 도구 자신이 서드파티 확장 모듈을 올리면 옮긴 뒤 지우기에서 같은 파일을 쥐므로
   표준 라이브러리만 쓴다.
5. `git worktree remove <경로>`. git 2.32 는 지우다 실패해도 등록을 지우고(`.scratch/harness/probes/
   worktree_longpath.py`), 그 폴더의 `.git` 파일도 지운다(`worktree_occupancy.py` 의 B·C·E).
6. `git branch -D <브랜치>`. squash 병합이라 `-d` 는 병합을 알아보지 못한다. 분리 HEAD 는 건너뛴다.
7. 휴지통 지우기. 옮긴 항목을 지운다. 링크(심볼릭 링크, 정션)는 따라가지 않고 링크 자체만 지운다.
   한 항목 안에서 파일 하나가 막히면 `shutil.rmtree` 가 그 자리에서 멈춰 아직 돌지 않은 형제도
   남는다(PR 직전 버그 리뷰가 파일 여덟 중 셋째를 연 채 재현해 다섯이 남았다). 막힌 항목은 쥔
   프로세스(작업 디렉터리와 모듈)를 들어 찍고 남긴다. 휴지통 자리 자신이 링크면 안을 읽지 않고
   넘긴다(`trash_dir`). 종료 코드는 바뀌지 않는다.
   워크트리와 브랜치는 이미 없다. 다음 `judge` 가 휴지통을 찍고 `empty-trash` 가 다시 지운다. 실제
   자식 파이썬이 `.venv` 아래 `.pyd` 를 올린 채로 워크트리와 브랜치가 지워지고 `.venv` 만 그 pid 와
   함께 휴지통에 남았으며, 자식이 끝난 뒤 `empty-trash` 가 비웠다(테스트, 윈도).

등록 없는 폴더(`remove-stray`, 대기열 148). `.claude/worktrees/` 바로 아래인데 등록이 없는 폴더다.
지우다 실패한 `git worktree remove` 가 등록과 `.git` 파일만 지우고 남긴 폴더와 빈 폴더가 쌓였다
(2026-10-12 에 일곱 가운데 빈 폴더 셋, 지우다 만 폴더 셋이었다. 손으로 봤다, 일지 2026-10-12-38).
그 안에서 git 은
루트에 닿아 판정 2를 내지 못하므로 내용으로 가른다. 아래 순서로 보고 처음 어긋난 것을 찍는다.
그 자리 자신이 링크(심볼릭 링크, 정션)면 안을 읽지 않고 넘긴다.
- `.git` 이 있으면 넘긴다. 어느 등록이 그 폴더를 잃었을 수 있다. 점유 탐침이 옆 이름에 남긴
  폴더이고 원래 이름의 등록이 폴더를 잃은 채 남아 있으면, 되돌릴 자리를 알린다.
- 읽다 막히면 남긴다.
- 링크가 있으면 남긴다. 다시 만들 수 있는 폴더(`RECREATABLE_DIRS` 의 이름, `RECREATABLE_PATHS` 의
  폴더 자리)는 링크여도 들어가지 않는다. `RECREATABLE_DIRS` 의 이름은 `.grimp_cache` 말고는 루트의
  `.gitignore` 가 어느 깊이에서나 무시한다(`.grimp_cache` 는 Grimp 가 그 안에 둔, `*` 줄이 든
  `.gitignore` 로 무시된다. 주 체크아웃의 것을 손으로 봤다). 그
  폴더의 `.gitignore` 는 지우다 만 폴더에서 먼저 지워졌을 수 있어 보지 않는다.
- 나머지 파일은 내용이 참조(브랜치, 원격, 태그, `refs/stash`)에서 닿는 커밋에 있어야 한다. 파일마다
  git 의 블롭 이름을 셈해 `git rev-list --all --objects` 와 견준다. git 이 텍스트로 보는 내용은 CRLF
  를 LF 로 바꾼 이름도 본다(`.gitattributes` 의 `* text=auto eol=lf`). 텍스트인지는 git 의
  판별(NUL, 홀로 쓰인 CR, 인쇄 문자 128개당 비인쇄 문자 하나를 넘는 비율)을 흉내 낸다. 그 판별은
  git 소스를 읽지 않고 알고 있던 것이고(어림), 테스트가 입력 몇에서 `git hash-object` 와 같은 이름을
  내는지 본다. 다시 만들 수 있는 파일과 루트와 같은 설정 파일(`settings_equivalent`)은 뺀다. 커밋에
  없는 파일(새 파일, 고친 파일, `.env`)이 하나라도 있으면 남긴다.
- 쥔 프로세스(판정 3의 작업 디렉터리와 모듈)가 있으면 남긴다.
`remove-stray` 는 그 자리가 `.claude/worktrees/` 바로 아래의 등록 없는 폴더인지 다시 보고, 판정을
다시 내고, 판정 4의 1의 탐침을 거쳐, 쥔 프로세스까지 넣어 다시 판정한 뒤 폴더째 휴지통으로 옮기고
지운다(판정 4의 7. 링크는 따라가지 않는다). git 은 그 폴더에서 부르지 않는다. 휴지통(`TRASH_DIR`)
자신은 등록 없는 폴더로 보지 않는다.
옆 이름(`.tidy-probe`)에 `.git` 과 함께 남은 폴더는 원래 이름의 등록이 폴더를 잃은 채 남아 있으면
`restore` 가 그 이름으로 되돌린다. 등록이 없거나 원래 이름에 무엇이 있으면 되돌리지 않는다.

쉬는 세션의 프로세스(`end-holders`). 판정 3이 `끝낸다`로 낸 워크트리의 쥔 프로세스를 끝낸다. 세션은
사이드바에 남는다. 2026-10-20 에 쉬는 세션 하나를 `taskkill /T /F` 로 끄고 손으로 봤다. 앱은 그
프로세스를 바로 다시 띄우지 않았고, 원격 제어에서는 그 세션이 절전이나 오프라인일 수 있다는 문구가
떴다. 다른 세션이 메시지를 보내자 앱이 그 세션을 다시 띄웠고 세션은 대화를 이어 답했다. 그
워크트리를 지운 뒤라 다시 뜬 세션의 작업 디렉터리는 주 체크아웃이었다. 아래 순서로 보고 어긋나면
아무것도 끄지 않는다.
1. 인자의 세션 id 가 모두 `local_<uuid>` 모양이고, 이 도구를 부른 세션을 환경으로 알며(앱 밖에서
   불러 모르면 끄지 않는다, PR 리뷰) 그 세션이 인자에 없다.
2. 그 경로가 등록된 워크트리다.
3. 프로세스를 다시 훑어 그 폴더를 작업 디렉터리로 쥔 프로세스와 산 잠금 pid 를 찾는다. 없으면
   끝낼 것 없이 0으로 끝난다.
4. 쥔 프로세스가 모두 인자의 세션 것이다. 하나라도 아니면 아무것도 끄지 않는다.
5. 판정 1~3을 다시 내어(실행 중 세션은 빼고) `끝낸다`가 나올 때만 간다. `judge` 뒤에 파일을 고쳤거나
   찍힌 적 없는 줄로 병합되지 않은 워크트리를 주면 끄지 않는다. `remove` 의 다시 판정과 짝이다.
   그 세션이 그사이 다시 돌기 시작했는지는 이 도구가 보지 못한다. 부르는 쪽이 이 명령을 치기
   직전에 `list_sessions` 로 다시 본다(스킬 3.2).
6. 프로세스마다 끄기 직전에 세션 id 를 다시 읽어, 훑을 때와 같을 때만 끈다(`end_process`). 훑은
   뒤 그 pid 가 끝나 다른 프로세스가 받았으면 값이 다르다. pid 만 보고 끄지 않는다
   (`.claude/rules/probes.md`). 윈도는 `taskkill /T /F` 로 그 아래 프로세스(셸, MCP 서버)까지
   끄고, 그 밖은 SIGTERM 을 그 프로세스에만 보낸다.
7. `END_WAITS` 만큼 기다리며 다시 훑어 쥔 프로세스가 없어지면 0으로 끝난다. 다음 `judge` 가 그
   워크트리를 다시 판정한다.

못 보는 것.
- 옮긴 뒤에 남은 추적 파일을 다른 프로세스가 워크트리 밖의 하드링크 이름으로 적재한 것.
  추적 파일은 하드링크가 아니라 드물다.
- 휴지통 항목을 쥔 프로세스의 매핑 이름은 옮기기 전 이름이다(윈도의 `GetMappedFileNameW`. 옮긴 뒤
  휴지통 자리로 견주니 빈 목록이었다, 테스트). 그래서 휴지통 자리와 그 항목이 옮겨지기 전 자리
  (`origin_of`. 자리 이름에서 거꾸로 셈한 어림이고 `WORKTREES_DIR` 아래였다고 본다) 둘로 견준다.
  워크트리가 다른 자리에 있었으면 쥔 프로세스를 대지 못하고 찾지 못했다고 적는다. 지우기 자체는
  막히면 남으므로 안전한 쪽이다.
- 체크아웃되지 않은 브랜치가 `origin/main` 에 든 것은 그 이름이 아직 쓰일 예정이었어도 reflog 의
  마지막 기록이 창(`FRESH_SECONDS`) 밖이면 지운다. 잃는 것은 이름이고 커밋은 `origin/main` 에
  있다.
- reflog 가 없는 브랜치(`core.logAllRefUpdates=false` 로 딴 것, 기록이 만료된 것). 막 딴 것인지
  몰라 판정 1대로 지운다. 잃는 것은 이름이다.
- 시계가 어긋난 PC 에서 남긴 앞날 시각의 기록. 막 딴 것으로 보아, 시계가 그 시각을 지나 창이 끝날
  때까지 정리마다 남긴다(남기는 쪽이다).
- `origin/main` 이 없는 저장소(얕은 클론, 클라우드 세션, 원격 없는 임시 저장소)에서는 어느 커밋도
  `origin/main` 에 닿지 않는 것으로 보여, 분리 HEAD 와 PR 없는 브랜치가 모두 남는다(안전한 쪽).
  이유 줄은 `origin/main 에 없다` 라고만 적는다.
- 휴지통 자리 이름의 역산(`origin_of`)은 이름에 `~~` 가 든 워크트리와 `~<숫자>` 로 끝나는 상대
  경로에서 어긋나 쥔 프로세스를 옛 자리로 찾지 못한다. 지우기는 그대로 막혀 남으니 안전한 쪽이다.
- 휴지통 자리 이름(`trash_slot`)이 파일 시스템이 경로 한 토막에 허용하는 길이(이 PC 의 NTFS 에서
  255자)를 넘는 항목. `judge` 는 지울 후보로 찍지만 `remove` 는 그 항목을 옮기다 막혀 남긴다(종료
  1). 다음 정리에서도 같은 자리에서 멈추는, 남기는 쪽이다(셀프 리뷰 명세 축이 재현했다).
- 탐침과 git 사이에 새로 생긴 점유와 파일. 다시 거른 뒤 git 이 지울 때까지의 틈이다.
- 세션이 쓰던 워크트리인지. 제목과 브랜치, 잠금, 작업 디렉터리로만 가린다(판정 3). 앱이 그 세션의
  CLI 를 띄워 두지 않았으면 작업 디렉터리로도 잡히지 않는다.
- 같은 이름으로 다시 딴 브랜치의 끝이 옛 병합된 PR 머리의 조상인 것(옛 PR 의 바탕보다 앞선 커밋에서
  땄다). 판정 1이 병합된 것으로 본다. 끝이 그 머리에 들어 잃는 커밋은 없고, 워크트리는 판정 2·3을
  그대로 본다.
- 쉬는 세션의 프로세스 가운데 판정 3의 작업 디렉터리로 쥔 것 말고는 끝내지 않는다. 모듈을 올린
  것과 등록 없는 폴더를 쥔 것은 그대로 남긴다. 환경에 `SESSION_ENV` 가 없는 프로세스(앱 밖에서 띄운
  CLI, 환경을 비우고 띄운 자식)는 세션을 모르는 것으로 보아 남긴다. 리눅스는 띄워질 때의 환경을
  읽고, 그 아래 프로세스는 끄지 않는다. 세션이 쉬는지는 보지 못해 부르는 쪽이 `--idle` 로 고른 것을
  믿는다.
- 폴더가 없거나 등록이 prunable 인 워크트리의 앱 표지. 읽지 않고 자리 판정대로 등록을 걷는다.
- 제목도 앱이 적은 브랜치도 그 브랜치 이름과 다른 세션. 앞뒤 공백이나 꼬리(`(인계함)`)가 붙은
  제목이 그렇고, 워크트리에서는 대소문자만 다른 제목도 그렇다(체크아웃되지 않은 브랜치에서는
  `same_branch` 가 같은 이름으로 본다). 판정 1이 지울 것으로 낸 체크아웃되지 않은 브랜치는 그런
  세션의 것이어도 대신 잡는 것이 없어 지울 후보로 찍힌다. 워크트리는 그 세션이 작업 디렉터리로
  쥐었으면 판정 3의 쥔 프로세스가 남긴다.
- `judge` 뒤에 열린 세션의 체크아웃되지 않은 브랜치. `remove-branch` 의 재판정은 세션을 보지
  않고(그 하위 명령은 제목을 받지 않는다), 워크트리의 `remove` 처럼 옮기기 직전에 쥔 프로세스를
  다시 보는 것도 없어 판정 1이 지울 것으로 낸 브랜치를 지운다. reflog 의 마지막 기록이 창 안인
  브랜치만 막 딴 것으로 남긴다.
- `judge` 가 워크트리 목록을 읽은 뒤 브랜치 목록을 읽기 전에 형제 세션이 체크아웃한 브랜치 가운데
  reflog 의 마지막 기록이 창 밖인 것. 체크아웃은 그 브랜치의 reflog 에 기록을 남기지 않아 지울
  후보로 찍힌다. `remove-branch` 가 워크트리 등록을 다시 읽어 남긴다.
- 맥과 리눅스의 점유. 재지 않았다. 그 OS 는 열린 파일과 작업 디렉터리가 이름 바꾸기를 막지 않는
  것으로 알고 있어(어림) 탐침이 점유를 보지 못한다고 본다. 리눅스에서 작업 디렉터리로 쥔 것은
  판정 3과 판정 4의 2가 남긴다. 2 뒤에 들어온 것은 위의 탐침과 git 사이의 틈과 같은 결로 보지
  못한다.
- 작업 디렉터리와 모듈 말고 다른 것으로 쥔 프로세스. 그 안의 파일을 연 프로세스
  (`lock_holder.py` 의 C)는 판정 3을 지나고, `remove` 에서 이름 바꾸기를 막아도 쥔 것을 찾지
  못했다고 적힌다.
- 열 수 없는 프로세스의 작업 디렉터리와 모듈. 2026-10-12 에 이 PC 의 프로세스 672개 중 493개의
  작업 디렉터리를 읽었다(`lock_holder.py --folder`). 읽지 못한 것은 건너뛴다. 그것이 무엇인지
  (다른 사용자, 높은 권한)는 재지 않았다.
- 32비트 프로세스. 건너뛰지 않고 64비트 PEB 를 읽는데, 그 사본은 32비트 코드가 바꾼 작업
  디렉터리를 따르지 않는다고 알고 있어 낡은 경로로 이름을 댈 수 있다(어림, 재지 않았다). 그
  프로세스가 올린 32비트 모듈은 `LIST_MODULES_ALL` 로 함께 읽는다고 알고 있다(어림, 재지 않았다).
- 윈도 폴더(`SystemRoot`) 아래 모듈의 다른 하드링크 이름. 펼치지 않는다.
- 등록 없는 폴더에서 `WHOLE_READ_LIMIT`(64MiB)를 넘는 파일의 줄 끝을 바꾼 이름. 덩이로 그대로의
  이름만 셈해, git 이 텍스트로 넣은 큰 파일은 커밋에 없는 것으로 보여 남는다(안전한 쪽).
- 드라이브 문자가 없는 장치(네트워크 공유, 문자 없는 마운트 지점)에서 올린 모듈. 매핑 이름을
  드라이브 경로로 바꾸지 못해 버린다.
- 등록 없는 폴더에서, 같은 내용이 다른 경로로 커밋된 파일과 빈 파일(참조에서 닿는 커밋에 빈 파일이
  하나라도 있으면). 커밋에 있는 것으로 본다. 내용은 그 참조가 남아 있는 동안 되살릴 수 있다. 같은
  정리에서 `remove-branch` 가 그 참조(병합된 브랜치)를 지우면 로컬에서는 닿지 않게 된다. 실행 비트와
  빈 폴더는 보지 않는다. 리플로그에만 남은 커밋과 맨 위가 아닌 stash 의 내용은 커밋에 없는 것으로
  보여 남는다(안전한 쪽). 텍스트 판별이 git 과 갈리면, 도구가 텍스트로 본 내용은 LF 이름까지 셈해
  줄 끝만 다른 내용을 커밋에 있는 것으로 보고(지우는 쪽, 줄 끝만 잃는다), 바이너리로 본 내용은
  그대로의 이름만 셈해 남긴다(안전한 쪽).

종료 코드. `judge`: 0 찍었다, 2 인자가 틀렸거나 주 체크아웃이 아니다, 3 git 이나 gh 가 실패했다.
`remove`·`remove-branch`: 0 지웠다(휴지통에 남은 것이 있으면 그 줄을 함께 찍는다). 1 망가뜨린 것
없이 멈췄다. 아무것도 바꾸지 않았거나(1·2에서 멈췄다), 죽은 잠금을 풀고 다시 만들 수 있는 것 일부를
휴지통으로 옮겼거나(4에서 멈췄다. 등록과 `.git` 이 남고 옮긴 것은 휴지통에서 지웠다), 워크트리는
지웠는데 브랜치가 남았다(6).
다음 후보로 가도 된다. 2 인자가 틀렸거나 주 체크아웃이 아니다. 3 멈추고 사람에게 넘긴다. 지우다 만
폴더나 옆 이름에 남은 폴더가 생겼을 수 있거나, git·gh 를 부르지 못했다.
`remove-stray`: 0 워크트리 자리에서 치웠다(휴지통에 남은 것이 있으면 그 줄을 함께 찍는다). 1
망가뜨린 것 없이 멈췄다(아무것도 바꾸지 않았다). 2·3 은 `remove` 와 같다.
`restore`: 0 되돌렸다. 1 되돌리지 않았다(옆 이름이 아니다, 등록이 없다, 원래 이름에 무엇이 있다,
막혔다). 2 는 `remove` 와 같다.
`empty-trash`: 0 휴지통이 비었다. 1 남은 것이 있다(항목마다 쥔 프로세스를 찍었다). 2 는 `remove` 와
같다.
`end-holders`: 0 쥔 프로세스를 끝냈다(쥔 것이 처음부터 없었어도 0). 1 아무것도 끄지 않았거나(이
도구를 부른 세션이거나 그 세션을 모른다, 등록된 워크트리가 아니다, 프로세스를 볼 수 없다, 받은 세션
밖의 프로세스가 쥐었다) 끈 뒤에도 쥔 것이 남았다. 2 세션 id 모양이 아니거나 `remove` 의 2와 같다.
3 은 `remove` 와 같다.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import functools
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import string
import subprocess
import sys
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

type Action = Literal["delete", "keep", "human", "hold", "restore", "end"]
type GitRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type ProcessPath = tuple[int, str, str]  # (pid, 실행 파일 이름, 작업 디렉터리나 모듈의 경로)
type HolderKind = Literal["cwd", "module", "lock"]

COMMAND = "uv run python tools/tidy_checkouts.py"
WORKTREES_DIR = ".claude/worktrees"
# 옆으로 옮겨 둔 무시된 항목이 쌓이는 자리. `WORKTREES_DIR` 바로 아래라 등록 없는 폴더 목록에서 뺀다
TRASH_DIR = WORKTREES_DIR + "/.tidy-trash"
SETTINGS = ".claude/settings.local.json"
OVERRIDES = "skillOverrides"
# `tools/hook_worktree_skill_overrides.py` 가 주 체크아웃의 local 설정에 적는 키의 접두(그 훅의
# `KEY_PREFIX` 와 같다. 시험이 그 상수로 키를 지어 대 본다).
WORKTREE_OVERRIDE_PREFIX = ".claude/worktrees/"
PROBE_SUFFIX = ".tidy-probe"
# 분리 HEAD 워크트리의 `remove` 인자. git 은 점으로 시작하는 브랜치 이름을 허락하지 않는다
# (`git check-ref-format --branch .detached` 가 128. 한 글자 `@` 는 이 PC 의 git 2.32 가 허락했다,
# 표준 축 리뷰가 임시 저장소에서 봤다). 셸이 풀 수 있는 글자(`_SHELL_UNSAFE`)도 들지 않는다
DETACHED = ".detached"
# 지우지 않는 브랜치. 루트가 다른 브랜치에 있을 때 `main` 이 체크아웃되지 않은 브랜치로 보인다
PROTECTED_BRANCHES = frozenset({"main", "master"})
MERGED_LIMIT = 1000
# gh 와 tasklist 하나를 기다리는 초. 넘기면 부르지 못한 것으로 센다(대기열 342). git 은 두지 않는다
# (`real_git`).
CALL_TIMEOUT = 60
# 막 딴 브랜치로 보는 창(초). reflog 의 마지막 기록이 이 안이면 PR 없이 끝이 `origin/main` 에 있어도
# 남긴다(대기열 440). `judge` 가 워크트리 목록과 브랜치 목록을 따로 읽는 틈과 `git worktree add -b`
# 가 브랜치를 먼저 따고 등록을 나중에 만드는 틈은 초 단위로 어림하고(재지 않았다), 브랜치를 먼저
# 따고 나중에 체크아웃하는 길까지 덮게 넉넉히 고른 값이다. 떠난 세션의 브랜치는 다음
# 정리가 지운다
FRESH_SECONDS = 3600
RECREATABLE_DIRS = frozenset(
    {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".import_linter_cache",
        ".grimp_cache",
        "node_modules",
        ".next",
        "test-results",
        "playwright-report",
        "blob-report",
        "coverage",
    }
)
RECREATABLE_FILES = frozenset({"next-env.d.ts"})
# Git Bash 의 grep·sh 가 죽으며 남기는 덤프(루트 `.gitignore` 의 `*.stackdump`)
RECREATABLE_SUFFIXES = (".stackdump",)
# 이름이 흔해 자리째로 본다. 폴더는 `/` 로 끝나고 파일은 그렇지 않다. 디자인 시스템 패키지의 빌드와
# 옛 `/design-sync`(번들 스킬의 빌드)가 산출물을 쓰던 자리(올리기는 더 쓰지 않지만 루트 `.gitignore`
# 가 남긴다, ADR 0025 의 2026-10-28 이력), 위젯의 Storybook 정적 빌드와 시작 래퍼가 복사한 글꼴
# 파일과 짓는 페이지 안 번들(대기열 464), 관리 화면의 Storybook 정적 빌드(admin-style 티켓 03), 소급
# 측정 프로브의 gh 응답 캐시(결과는 `branches.json` 에 커밋한다). 모두 루트 `.gitignore`
# 가 앵커를 붙여 무시한다. 플랜 모드의 계획 파일 `.claude/plans/` 는 산출물이 아니라 세션의 계획
# 원문이라 넣지 않는다(명세 축 리뷰)
RECREATABLE_PATHS = frozenset(
    {
        "web/packages/ui/dist/",
        "web/packages/ui/storybook-static/",
        "web/apps/widget/storybook-static/",
        "web/apps/widget/public/fonts/",
        "web/apps/widget/public/element.js",
        "web/apps/admin/storybook-static/",
        ".ds-sync/",
        "ds-bundle/",
        ".design-sync/sb-reference/",
        ".design-sync/.cache/",
        ".scratch/harness/probes/session_cost/cache/",
    }
)

_LOCK_PID = re.compile(r"^claude session \S+ \(pid (\d+)\)$")
# 찍은 명령을 에이전트가 셸에 그대로 친다. git 은 브랜치 이름에 `$`·`;`·`(`·백틱을 허락해, 그런
# 이름이 든 명령은 찍지 않고 사람에게 넘긴다(셀프 보안 리뷰, 일지 2026-10-07-15)
_SHELL_UNSAFE = re.compile(r"[\s$`\"'\\;&|<>(){}*?\[\]!#~]")
_ACTIONS: dict[Action, str] = {
    "delete": "지운다",
    "keep": "남긴다",
    "human": "넘긴다",
    "hold": "넘긴다",
    "restore": "되돌린다",
    "end": "끝낸다",
}
_HOLDER_LABELS: dict[HolderKind, str] = {
    "cwd": "작업 디렉터리로 쥔 프로세스",
    "module": "모듈을 올린 프로세스",
    "lock": "잠금 pid",
}
# 판정 3에서 제목이나 브랜치(`list_sessions` 의 `branch`)가 그 브랜치인 실행 중 세션 때문에 남긴
# 이유. 워크트리와 체크아웃되지 않은 브랜치가 같이 쓴다
_RUNNING_REASON = "제목이나 브랜치가 그 브랜치인 세션이 돈다"
# 판정 1에서 브랜치 끝이 병합된 PR 머리의 조상이라 지우는 이유
_BEHIND_REASON = "브랜치 끝이 병합된 PR 의 머리보다 뒤다. 로컬에만 있는 커밋이 없다"
# 판정 1에서 PR 없이 끝이 `origin/main` 에 있는데 reflog 의 마지막 기록이 창 안이라 남긴 이유
_FRESH_REASON = (
    f"막 딴 브랜치다. reflog 의 마지막 기록이 {FRESH_SECONDS // 60}분 안이거나 앞날이다"
    " (나란히 연 세션이 체크아웃하기 전일 수 있다)"
)
# git 의 텍스트 판별에서 비인쇄로 세는 바이트. 32 아래에서 백스페이스·탭·ESC·폼 피드와 CR·LF 를 뺀
# 것과 DEL 이다(`looks_text`)
_NONPRINTABLE = bytes(byte for byte in [*range(32), 127] if byte not in (8, 9, 10, 12, 13, 27))
# 등록 없는 폴더의 파일을 통째로 읽어 블롭 이름을 셈하는 크기의 상한(바이트). 넘으면 덩이로
# 읽는다(`file_blob_ids`, PR 직전 버그·성능 리뷰)
WHOLE_READ_LIMIT = 64 * 1024 * 1024
# 되돌리기를 다시 시도하기 전에 기다리는 초. 옮기기가 지난 뒤 되돌리기가 `WinError 5` 로 한 번
# 막혔다(대기열 202). 무엇이 그 틈에 폴더를 쥐었는지는 재지 않았다
RESTORE_WAITS = (0.2, 0.5, 1.0, 2.0)
# 데스크톱 앱이 자기 워크트리의 git 디렉터리(`.git/worktrees/<이름>/`)에 두는 표지. 앱의 정리
# (`[WorktreePool]`)는 이 표지가 있는 워크트리만 지운다(ADR 0032)
APP_MARKER = "claude-desktop-worktree"
# 데스크톱 앱이 세션의 `claude.exe` 환경에 넣는 세션 id. 그 아래 프로세스도 물려받는다(2026-10-20
# 에 이 PC 의 세션 프로세스 환경을 PEB 에서 읽어 손으로 봤다)
SESSION_ENV = "CLAUDE_CODE_HOST_SESSION_ID"
_SESSION_ID = re.compile(r"local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# `end-holders` 가 프로세스를 끈 뒤 쥔 것이 사라졌는지 다시 보기 전에 기다리는 초. 끄기를 부른
# 뒤에도 프로세스가 끝나기까지 틈이 있다(어림, 재지 않았다)
END_WAITS = (0.2, 0.5, 1.0, 2.0)


class ToolError(Exception):
    """git 이나 gh 를 부르지 못했다. 판정을 낼 수 없다."""


@dataclass(frozen=True)
class Worktree:
    """`git worktree list --porcelain` 의 한 항목. `locked` 는 잠금 사유다(사유가 없으면 "")."""

    path: str
    head: str | None = None
    branch: str | None = None
    locked: str | None = None
    prunable: bool = False
    bare: bool = False


@dataclass(frozen=True)
class Facts:
    """판정 2와 자리 판정의 재료. 자리가 어긋나면 status 를 읽지 않아 빈 값이다. `aside` 는 점유
    탐침의 옆 이름 폴더가 있다는 뜻이고, `contained` 는 HEAD 가 `origin/main` 에서 닿는다는 뜻이다
    (분리 HEAD 에서만 읽는다). `behind` 는 브랜치 끝이 이름이 같은 병합된 PR 의 머리 가운데 하나의
    조상이라는 뜻이고(끝이 머리와 같으면 읽지 않는다), `app_marker` 는 앱의 표지(`APP_MARKER`)가
    있다는 뜻이다. `tracked_links` 는 추적 파일이 든 폴더 가운데 링크인 것이다(같은 이름의 함수)."""

    exists: bool
    toplevel: str | None
    status: str
    status_err: str
    ignored: tuple[str, ...]
    settings_same: bool
    aside: bool = False
    contained: bool = False
    has_git: bool = True
    behind: bool = False
    app_marker: bool = False
    tracked_links: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    """`hold` 는 지울 것이었는데 제목 모를 세션 때문에 넘긴 것이다. 사람이 승인하면 지운다.
    `human` 은 사람이 직접 본다. `unlock` 은 지우기 전에 죽은 잠금을 풀어야 한다는 뜻이다. `end` 는
    지울 것이었는데 쉬는 세션의 프로세스만 쥐어, `sessions` 의 프로세스를 끝내면 지울 수 있다는
    뜻이다."""

    action: Action
    path: str
    reason: str
    branch: str | None = None
    head: str | None = None
    unlock: bool = False
    sessions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Holder:
    """워크트리 폴더를 쥔 프로세스. `image` 는 실행 파일 이름이다(모르면 ""). `kind` 는 쥔 모양이다.
    `cwd` 는 작업 디렉터리로, `module` 은 그 아래 파일(하드링크 이름 포함)을 모듈로 올려 쥐었다."""

    pid: int
    image: str
    kind: HolderKind = "cwd"


# --- 바깥을 부르는 것 ---------------------------------------------------------------------------


def real_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """`GIT_OPTIONAL_LOCKS=0`: 남의 워크트리에서 친 `status` 가 색인을 고쳐 쓰며 잠그지 않는다.
    시간 제한을 두지 않는다. 지우는 git(`worktree remove`, `branch -D`)도 이 길로 가고, 큰
    `node_modules` 를 지우는 중에 끊으면 지우다 만 폴더가 남는다. 이 도구의 git 은 모두 이 함수
    하나로 가서 읽기만 하는 git(`status --ignored=matching`, `ls-files`, `for-each-ref`, `log -g`,
    `merge-base`, `rev-parse`, `rev-list`, `worktree list` 등)도 함께 시간 제한이 없다. 그것만
    끊으려면 `Ops.git` 을 지우는 길과 읽는 길로 가르거나, 이 함수가 하위 명령으로 갈라 읽는 길에만
    시간 제한을 준다."""
    return subprocess.run(  # 시간 제한 없음: 지우는 git 도 이 길로 가 도중에 끊지 않는다(독스트링)
        ["git", "-c", "core.longpaths=true", *args],
        cwd=cwd,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def gh_merged_heads(root: Path) -> dict[str, frozenset[str]]:
    fields = "headRefName,headRefOid"
    command = ["gh", "pr", "list", "--state", "merged", "--limit", str(MERGED_LIMIT)]
    try:
        result = subprocess.run(
            [*command, "--json", fields],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=CALL_TIMEOUT,
        )
    except OSError as error:
        raise ToolError(f"gh 를 띄우지 못했다: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise ToolError(f"gh pr list 가 {CALL_TIMEOUT}초 안에 돌아오지 않았다") from error
    if result.returncode != 0:
        raise ToolError(f"gh pr list 가 {result.returncode} 로 끝났다: {result.stderr.strip()}")
    try:
        return parse_merged(result.stdout)
    except ValueError as error:
        raise ToolError(f"gh pr list 의 출력을 읽지 못했다: {error}") from error


def process_alive(pid: int) -> bool:
    """그 pid 의 프로세스가 있는지. 알 수 없으면(`tasklist` 가 시간을 넘긴 것도) 있다고 본다(지우지
    않는 쪽)."""
    if sys.platform == "win32":
        query = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
        try:
            result = subprocess.run(
                query, capture_output=True, text=True, errors="replace", timeout=CALL_TIMEOUT
            )
        except (OSError, subprocess.TimeoutExpired):
            return True
        return result.returncode != 0 or tasklist_has(result.stdout, pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _linux_cwds() -> list[ProcessPath]:
    """`/proc/<pid>/cwd` 를 읽는다. 읽을 수 없는 프로세스(다른 사용자의 것)는 건너뛴다."""
    found: list[ProcessPath] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            cwd = os.readlink(f"/proc/{entry}/cwd")
        except OSError:
            continue
        try:
            image = os.path.basename(os.readlink(f"/proc/{entry}/exe"))
        except OSError:
            image = ""
        found.append((int(entry), image, cwd))
    return found


def _linux_session(pid: int) -> str | None:
    """`/proc/<pid>/environ` 의 세션 id. 프로세스가 띄워질 때의 환경이다."""
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return None
    return session_in(raw.decode("utf-8", errors="replace").split("\0"))


if sys.platform == "win32":
    _QUERY_LIMITED = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
    _VM_READ = 0x0010  # PROCESS_VM_READ
    _INHERIT_HANDLE = False  # bInheritHandle. 자식 프로세스에 핸들을 물려주지 않는다
    # x64 의 자리: PEB.ProcessParameters, 그 안의 CurrentDirectory.DosPath(UNICODE_STRING),
    # Environment(포인터), EnvironmentSize(바이트)
    _PEB_PARAMS = 0x20
    _PARAMS_CWD = 0x38
    _PARAMS_ENV = 0x80
    _PARAMS_ENV_SIZE = 0x3F0
    # 환경 블록을 읽는 크기의 상한(바이트). 넘으면 읽지 않는다
    _ENV_LIMIT = 1 << 20
    _LIST_MODULES_ALL = 0x03  # 32비트와 64비트 모듈 모두
    _LONG_PATH = 32768
    _INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _BasicInformation(ctypes.Structure):
        """PROCESS_BASIC_INFORMATION. `peb` 가 그 프로세스 안의 PEB 주소다."""

        _fields_ = [
            ("exit_status", ctypes.c_void_p),
            ("peb", ctypes.c_void_p),
            ("affinity", ctypes.c_void_p),
            ("priority", ctypes.c_void_p),
            ("pid", ctypes.c_void_p),
            ("parent", ctypes.c_void_p),
        ]

    def _windows_api() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
        """핸들과 포인터가 64비트에서 잘리지 않게 원형을 적은 kernel32 와 ntdll."""
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        dword, handle, pointer = ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p
        kernel.OpenProcess.restype = handle
        kernel.OpenProcess.argtypes = [dword, ctypes.c_int, dword]
        kernel.CloseHandle.argtypes = [handle]
        kernel.ReadProcessMemory.argtypes = [
            handle,
            pointer,
            pointer,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel.QueryFullProcessImageNameW.argtypes = [
            handle,
            dword,
            ctypes.c_wchar_p,
            ctypes.POINTER(dword),
        ]
        kernel.K32EnumProcesses.argtypes = [ctypes.POINTER(dword), dword, ctypes.POINTER(dword)]
        kernel.K32EnumProcessModulesEx.argtypes = [
            handle,
            ctypes.POINTER(ctypes.c_void_p),
            dword,
            ctypes.POINTER(dword),
            dword,
        ]
        kernel.K32GetMappedFileNameW.argtypes = [handle, pointer, ctypes.c_wchar_p, dword]
        kernel.QueryDosDeviceW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, dword]
        kernel.FindFirstFileNameW.restype = handle
        kernel.FindFirstFileNameW.argtypes = [
            ctypes.c_wchar_p,
            dword,
            ctypes.POINTER(dword),
            ctypes.c_wchar_p,
        ]
        kernel.FindNextFileNameW.argtypes = [handle, ctypes.POINTER(dword), ctypes.c_wchar_p]
        kernel.FindClose.argtypes = [handle]
        ntdll.NtQueryInformationProcess.argtypes = [handle, ctypes.c_int, pointer, dword, pointer]
        return kernel, ntdll

    def _windows_pids(kernel: ctypes.WinDLL) -> list[int]:
        size = 1024
        while True:
            array = (ctypes.c_ulong * size)()
            used = ctypes.c_ulong()
            if not kernel.K32EnumProcesses(array, ctypes.sizeof(array), ctypes.byref(used)):
                return []
            count = used.value // ctypes.sizeof(ctypes.c_ulong)
            if count < size:
                return list(array[:count])
            size *= 2

    def _read_memory(kernel: ctypes.WinDLL, handle: int, address: int, size: int) -> bytes | None:
        buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not kernel.ReadProcessMemory(handle, address, buffer, size, ctypes.byref(got)):
            return None
        return buffer.raw if got.value == size else None

    def _peb_params(kernel: ctypes.WinDLL, ntdll: ctypes.WinDLL, handle: int) -> int | None:
        """그 프로세스 안의 RTL_USER_PROCESS_PARAMETERS 주소."""
        info = _BasicInformation()
        size = ctypes.sizeof(info)
        status = ntdll.NtQueryInformationProcess(handle, 0, ctypes.byref(info), size, None)
        peb = info.peb
        if status != 0 or not isinstance(peb, int):
            return None
        raw = _read_memory(kernel, handle, peb + _PEB_PARAMS, 8)
        return None if raw is None else int.from_bytes(raw, "little")

    def _peb_cwd(kernel: ctypes.WinDLL, ntdll: ctypes.WinDLL, handle: int) -> str | None:
        params = _peb_params(kernel, ntdll, handle)
        if params is None:
            return None
        raw = _read_memory(kernel, handle, params + _PARAMS_CWD, 16)
        if raw is None:
            return None
        length = int.from_bytes(raw[0:2], "little")
        buffer = int.from_bytes(raw[8:16], "little")
        if length == 0 or buffer == 0:
            return None
        text = _read_memory(kernel, handle, buffer, length)
        return text.decode("utf-16-le", errors="replace") if text is not None else None

    def _peb_environment(kernel: ctypes.WinDLL, ntdll: ctypes.WinDLL, handle: int) -> str | None:
        """환경 블록(`이름=값` 들을 NUL 로 이은 것). 지금의 환경이다."""
        params = _peb_params(kernel, ntdll, handle)
        if params is None:
            return None
        pointer = _read_memory(kernel, handle, params + _PARAMS_ENV, 8)
        size = _read_memory(kernel, handle, params + _PARAMS_ENV_SIZE, 8)
        if pointer is None or size is None:
            return None
        length = int.from_bytes(size, "little")
        if not 0 < length <= _ENV_LIMIT:
            return None
        block = _read_memory(kernel, handle, int.from_bytes(pointer, "little"), length)
        return block.decode("utf-16-le", errors="replace") if block is not None else None

    def _windows_session(pid: int) -> str | None:
        """그 프로세스 환경 블록의 세션 id. x64 의 자리만 안다."""
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            return None
        kernel, ntdll = _windows_api()
        handle = kernel.OpenProcess(_QUERY_LIMITED | _VM_READ, _INHERIT_HANDLE, pid)
        if not handle:
            return None
        try:
            text = _peb_environment(kernel, ntdll, handle)
        finally:
            kernel.CloseHandle(handle)
        return None if text is None else session_in(text.split("\0"))

    def _image_name(kernel: ctypes.WinDLL, handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return os.path.basename(buffer.value)

    def _windows_cwds() -> list[ProcessPath] | None:
        """프로세스마다 PEB 의 작업 디렉터리를 읽는다. 열지 못하는 프로세스는 건너뛴다.

        x64 의 자리만 안다. 32비트 파이썬이면 None 이다.
        """
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            return None
        kernel, ntdll = _windows_api()
        found: list[ProcessPath] = []
        for pid in _windows_pids(kernel):
            handle = kernel.OpenProcess(_QUERY_LIMITED | _VM_READ, _INHERIT_HANDLE, pid)
            if not handle:
                continue
            try:
                cwd = _peb_cwd(kernel, ntdll, handle)
                if cwd is not None:
                    found.append((pid, _image_name(kernel, handle), cwd))
            finally:
                kernel.CloseHandle(handle)
        return found

    def _drives(kernel: ctypes.WinDLL) -> dict[str, str]:
        """장치 경로(`\\Device\\HarddiskVolume2`)에서 드라이브(`C:`)로."""
        found: dict[str, str] = {}
        buffer = ctypes.create_unicode_buffer(1024)
        for letter in string.ascii_uppercase:
            if kernel.QueryDosDeviceW(f"{letter}:", buffer, len(buffer)):
                found[buffer.value] = f"{letter}:"
        return found

    def _module_paths(kernel: ctypes.WinDLL, handle: int, drives: Mapping[str, str]) -> list[str]:
        """그 프로세스가 적재한 모듈(실행 파일 자신 포함)의 경로. 읽지 못하면 빈 목록.

        이름은 `GetMappedFileNameW` 로 읽는다. `GetModuleFileNameExW` 로 읽는 훑기 고리 전체가
        프로세스 743개(모듈 2만 8천여 개)에서 5.5초였고, 모듈 목록과 이 길만 따로 재니
        0.6초였다(스크래치 스크립트로 손으로 봤다. 두 스크립트의 잰 범위가 같지 않다, 일지
        2026-10-12-38). 바꾼 판의 훑기 전체는 `module_holder.py` 에서 1초 안팎이었다. 앞의 길이 느린
        까닭은 재지 않았다.
        """
        size = 512
        while True:
            array = (ctypes.c_void_p * size)()
            needed = ctypes.c_ulong()
            listed = kernel.K32EnumProcessModulesEx(
                handle, array, ctypes.sizeof(array), ctypes.byref(needed), _LIST_MODULES_ALL
            )
            if not listed:
                return []
            count = needed.value // ctypes.sizeof(ctypes.c_void_p)
            if count <= size:
                break
            size = count
        buffer = ctypes.create_unicode_buffer(_LONG_PATH)
        paths: list[str] = []
        for module in array[:count]:
            if module is None or not kernel.K32GetMappedFileNameW(
                handle, module, buffer, len(buffer)
            ):
                continue
            path = dos_path(buffer.value, drives)
            if path is not None:
                paths.append(path)
        return paths

    def _link_names(kernel: ctypes.WinDLL, path: str) -> list[str]:
        """같은 파일의 하드링크 이름 전부(`path` 자신 포함). 읽지 못하면 빈 목록.

        `FindFirstFileNameW` 는 드라이브 없는 경로를 주어 `path` 의 드라이브를 붙인다. 하드링크는
        같은 볼륨 안에만 있다.
        """
        drive = os.path.splitdrive(_without_long_prefix(path))[0]
        buffer = ctypes.create_unicode_buffer(_LONG_PATH)
        length = ctypes.c_ulong(len(buffer))
        found = kernel.FindFirstFileNameW(long_path(path), 0, ctypes.byref(length), buffer)
        if found is None or found == _INVALID_HANDLE:
            return []
        names: list[str] = []
        try:
            while True:
                names.append(drive + buffer.value)
                length = ctypes.c_ulong(len(buffer))
                if not kernel.FindNextFileNameW(found, ctypes.byref(length), buffer):
                    return names
        finally:
            kernel.FindClose(found)

    def _windows_modules() -> list[ProcessPath] | None:
        """프로세스마다 적재한 모듈의 경로와 그 파일의 다른 하드링크 이름. 열지 못하는 프로세스는
        건너뛴다. 윈도 폴더 아래 모듈은 링크를 펼치지 않는다(그 링크는 WinSxS 안에 있다고 알고
        있다, 어림)."""
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            return None
        kernel, _ = _windows_api()
        drives = _drives(kernel)
        loaded: list[tuple[int, str, str]] = []
        for pid in _windows_pids(kernel):
            handle = kernel.OpenProcess(_QUERY_LIMITED | _VM_READ, _INHERIT_HANDLE, pid)
            if not handle:
                continue
            try:
                image = _image_name(kernel, handle)
                modules = _module_paths(kernel, handle, drives)
                loaded.extend((pid, image, path) for path in modules)
            finally:
                kernel.CloseHandle(handle)
        system = os.environ.get("SystemRoot", "C:\\Windows")
        names: dict[str, list[str]] = {}
        for _, _, path in loaded:
            if path not in names:
                names[path] = [] if is_within(path, system) else _link_names(kernel, path)
        found: list[ProcessPath] = []
        for pid, image, path in loaded:
            found.append((pid, image, path))
            found.extend((pid, image, name) for name in names[path] if not same_path(name, path))
        return found


def _process_cwds() -> list[ProcessPath] | None:
    """프로세스마다 (pid, 실행 파일 이름, 작업 디렉터리). 이 OS 에서 볼 수 없으면 None."""
    if sys.platform == "win32":
        return _windows_cwds()
    if sys.platform == "linux":
        return _linux_cwds()
    return None


def scan_processes() -> list[ProcessPath] | None:
    """프로세스마다 (pid, 실행 파일 이름, 작업 디렉터리). 이 OS 에서 볼 수 없거나 읽다 실패하면
    None.

    `judge` 는 한 번에 한 번(판정 3) 부른다. `remove` 는 점유 탐침이 막히면 이유를 대려고(판정 4의
    1), 지나가면 옮기기 직전의 다시 거르기에서(판정 4의 2) 한 번 부른다.
    """
    try:
        return _process_cwds()
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        # DLL 이나 함수를 싣지 못했거나(OSError, AttributeError) 인자를 바꾸지 못했다. 읽다 난
        # 실패가 판정과 이유 줄을 지우지 않게 볼 수 없는 것으로 돌려준다(PR #182 claude-review)
        return None


def scan_modules() -> list[ProcessPath] | None:
    """프로세스마다 (pid, 실행 파일 이름, 적재한 모듈의 경로나 그 파일의 다른 하드링크 이름).
    윈도 밖이거나 읽다 실패하면 None. 부르는 때는 `scan_processes` 와 같다."""
    if sys.platform != "win32":
        return None
    try:
        return _windows_modules()
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return None


def process_session(pid: int) -> str | None:
    """그 프로세스 환경의 세션 id(`SESSION_ENV`). 없거나, 모양(`local_<uuid>`)이 어긋나거나, 이
    OS 에서 읽을 수 없거나, 읽다 실패하면 None. 윈도는 PEB 의 환경 블록을, 리눅스는
    `/proc/<pid>/environ` 을 읽는다."""
    try:
        if sys.platform == "win32":
            return _windows_session(pid)
        if sys.platform == "linux":
            return _linux_session(pid)
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return None
    return None


def end_process(pid: int) -> bool:
    """그 프로세스를 끝낸다. 윈도는 `taskkill /T /F` 로 그 아래 프로세스까지 끝내고, 그 밖은
    SIGTERM 을 그 프로세스에만 보낸다. 이미 없으면 끝낸 것으로 본다."""
    if sys.platform == "win32":
        command = ["taskkill", "/PID", str(pid), "/T", "/F"]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, errors="replace", timeout=CALL_TIMEOUT
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 or not process_alive(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return True


def holders_in(
    processes: Sequence[ProcessPath] | None, folder: str, kind: HolderKind = "cwd"
) -> list[Holder] | None:
    """경로가 `folder` 이거나 그 아래인 프로세스를 pid 마다 하나. 볼 수 없었으면(None) None."""
    if processes is None:
        return None
    found: dict[int, Holder] = {}
    for pid, image, path in processes:
        if pid not in found and is_within(path, folder):
            found[pid] = Holder(pid, image, kind)
    return list(found.values())


def cwd_holders(folder: Path) -> list[Holder] | None:
    """한 폴더만 볼 때. 훑기와 거르기를 한 번에 한다(프로브 `lock_holder.py` 가 부른다)."""
    return holders_in(scan_processes(), str(folder))


def long_path(path: str | os.PathLike[str]) -> str:
    """윈도에서 MAX_PATH 를 넘는 경로를 파이썬이 다루도록 `\\\\?\\` 를 붙인 절대 경로.

    이미 절대 경로면 정규화하지 않고 구분자만 바꾼다. `os.path.abspath` 는 끝의 점과 공백을 떼고
    `nul` 같은 장치 이름을 장치로 바꿔, 등록 없는 폴더의 `trail.` 을 `trail` 로 읽고 그 폴더를 지울
    것으로 냈다(PR 직전 버그 리뷰가 손으로 재현했다). 그래서 `..` 이 든 절대 경로는 받지 않는다
    (`\\\\?\\` 경로에서 풀리지 않아 OSError 로 멈춘다).
    """
    text = os.fspath(path)
    if sys.platform != "win32":
        return os.path.abspath(text)
    if text.startswith("\\\\?\\"):
        return text
    if not os.path.isabs(text):
        text = os.path.abspath(text)
    text = text.replace("/", "\\")
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def _writable_retry(function: Callable[[str], object], target: str, error: BaseException) -> None:
    """읽기 전용 파일이면 쓰기를 켜고 한 번 더 지운다. 그래도 막히면 그 예외로 멈춘다."""
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(target, stat.S_IWRITE)
    function(target)


def holds_home(path: str | os.PathLike[str], home: str | os.PathLike[str]) -> bool:
    """`path` 가 드라이브 뿌리이거나 `home` 이거나 그 조상인지. 링크, 짧은 이름, `..`, 상대 경로는
    `os.path.realpath` 로 가리키는 자리로 풀어 견준다.

    티켓 07의 셀프 리뷰에서 서브에이전트가 브리프대로 `cut_links("C:\\")` 를 불러 사용자 프로필의
    junction 열셋을 끊었다(일지 2026-10-23-45 사고 절). 그래서 지우는 두 함수(`cut_links`,
    `delete_path`)는 이 자리를 받으면 지우지 않는다.

    못 보는 것: `realpath` 로 푼 자리가 드라이브 뿌리나 홈, 그 조상이 아니면 막지 않는다. 홈 아래의
    폴더(그 안의 링크는 끊는다), 홈 밖의 다른 자리(이 저장소의 주 체크아웃, 홈이 없는 드라이브의
    폴더), 같은 자리를 다른 꼴로 가리키는 경로(UNC 관리 공유 `\\\\localhost\\C$\\Users\\<이름>`)가
    그 예다. 지우는 두 함수는 홈을 `os.path.expanduser("~")` 로 얻어, 그 값이 홈이 아니면 그 값의
    자리를 대신 견준다. 윈도에서 `USERPROFILE` 이 빈 값이면 그 값이 빈 문자열이라 작업 폴더와 그
    조상을 막고 홈은 막지 않는다.
    """
    target = os.path.realpath(path)
    if os.path.dirname(target) == target:
        return True
    return is_within(os.path.realpath(home), target)


def delete_path(path: Path) -> None:
    """무시된 항목 하나를 지운다. 링크는 따라가지 않고 링크 자체만 지운다. 막히면 OSError. 링크가
    아닌 드라이브 뿌리나 홈, 그 조상(`holds_home`)이면 지우지 않고 PermissionError 다. 링크는 홈이나
    그 조상을 가리켜도, 홈 자체가 링크여도 그 링크만 지운다."""
    target = long_path(path)
    if os.path.islink(target) or os.path.isjunction(target):
        os.unlink(target)
    elif holds_home(path, os.path.expanduser("~")):
        raise PermissionError(f"드라이브 뿌리나 홈, 그 조상은 지우지 않는다: {path}")
    elif os.path.isdir(target):
        shutil.rmtree(target, onexc=_writable_retry)
    elif os.path.lexists(target):
        try:
            os.unlink(target)
        except PermissionError as error:
            _writable_retry(os.unlink, target, error)


def cut_links(folder: str | os.PathLike[str]) -> list[str]:
    """`folder` 아래의 심볼릭 링크와 junction 을 링크만 끊는다. 끊지 못한 링크와 읽지 못한 폴더를
    준다. 링크 안으로는 내려가지 않는다. `folder` 자체가 링크이거나 드라이브 뿌리나 홈, 그
    조상(`holds_home`)이면 아무것도 끊지 않고 그것을 준다.

    git 2.32 의 `git worktree remove --force` 는 꺼낸 자리 안의 junction 을 따라가 그 바깥 폴더의
    파일까지 지웠다(일지 2026-10-15-19). 그래서 작업 트리나 회차 폴더를 걷기 전에 부른다. 윈도의
    junction 도 `os.unlink` 가 링크만 지운다. 뿌리가 링크일 때 따라가면 그 링크가 가리키는 바깥
    트리의 링크를 모두 끊는다(티켓 07의 커밋 전 반박 검증이 링크로 바뀐 게이트 작업 트리 자리로
    재현했다). 다시 풀기의 도구들(`tools/rerun_round.py`, `tools/rerun_hidden.py`,
    `tools/rerun_gates.py`)이 함께 쓴다. `tools/canary.py` 는 경로로 띄우는 스크립트라 `tools`
    패키지를 가져오지 못해 사본(`_cut_links`)을 따로 둔다. 그 사본에는 뿌리 링크, 긴 경로, 홈
    가드의 고침이 없다(대기열 451).

    훑기와 끊기는 `long_path` 로 한다. 윈도에서 긴 경로가 꺼져 있으면 MAX_PATH(260자)에 걸리는 깊은
    폴더(게이트 작업 트리의 `web/node_modules/.pnpm` 아래)를 평범한 경로로 읽지 못해 그 폴더를
    끊지 못한 것으로 냈다(티켓 07의 PR 직전 bug-perf-review). 돌려주는 경로는 넘긴 `folder` 를
    머리로 두고 그 아래를 `os.path.join` 으로 잇는다. 읽지 못한 뿌리는 넘긴 꼴 그대로 준다. `..` 이
    든 절대 경로는 `long_path` 가 풀지 않아 `folder` 를 읽지 못한 폴더로 준다. 그러면 다시 풀기의
    세 도구는 지우거나 걷지 않고 알린다.
    """
    root = os.fspath(folder)
    scan_root = long_path(root)
    if (
        os.path.islink(scan_root)
        or os.path.isjunction(scan_root)
        or holds_home(root, os.path.expanduser("~"))
    ):
        return [root]

    def shown(path: str) -> str:
        # `long_path` 가 끝 구분자를 뗀 뿌리(상대 경로, 리눅스의 절대 경로)에 이어 붙이면
        # 구분자가 겹친다
        rest = path[len(scan_root) :].lstrip(os.sep)
        return os.path.join(root, rest) if rest else root

    left: list[str] = []
    pending = [scan_root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            left.append(shown(current))
            continue
        for entry in entries:
            if entry.is_symlink() or entry.is_junction():
                try:
                    os.unlink(entry.path)
                except OSError:
                    left.append(shown(entry.path))
            elif entry.is_dir(follow_symlinks=False):
                pending.append(entry.path)
    return left


@dataclass(frozen=True)
class Ops:
    """바깥을 부르는 자리. 테스트가 실패를 넣는다."""

    git: GitRunner = real_git
    merged: Callable[[Path], dict[str, frozenset[str]]] = gh_merged_heads
    pid_alive: Callable[[int], bool] = process_alive
    rename: Callable[[str, str], None] = os.rename
    delete: Callable[[Path], None] = delete_path
    processes: Callable[[], list[ProcessPath] | None] = scan_processes
    modules: Callable[[], list[ProcessPath] | None] = scan_modules
    sleep: Callable[[float], None] = time.sleep
    session_of: Callable[[int], str | None] = process_session
    end: Callable[[int], bool] = end_process
    now: Callable[[], float] = time.time


def holders_from(
    processes: Sequence[ProcessPath] | None, modules: Sequence[ProcessPath] | None, folder: str
) -> list[Holder] | None:
    """훑은 작업 디렉터리와 모듈에서 `folder` 를 쥔 프로세스."""
    return combine_holders(holders_in(processes, folder), holders_in(modules, folder, "module"))


def holders_now(ops: Ops, folder: str) -> list[Holder] | None:
    """`folder` 를 작업 디렉터리로 쥐었거나 그 아래 모듈을 올린 프로세스. 훑기를 한 번씩 한다."""
    return holders_from(ops.processes(), ops.modules(), folder)


# --- 읽기 ---------------------------------------------------------------------------------------


def parse_worktrees(porcelain: str) -> list[Worktree]:
    worktrees: list[Worktree] = []
    fields: dict[str, str] = {}
    for line in [*porcelain.splitlines(), ""]:
        if line:
            key, _, value = line.partition(" ")
            fields[key] = value
            continue
        if "worktree" in fields:
            branch = fields.get("branch")
            worktrees.append(
                Worktree(
                    path=fields["worktree"],
                    head=fields.get("HEAD"),
                    branch=branch.removeprefix("refs/heads/") if branch is not None else None,
                    locked=fields.get("locked"),
                    prunable="prunable" in fields,
                    bare="bare" in fields,
                )
            )
        fields = {}
    return worktrees


def lock_pid(reason: str) -> int | None:
    match = _LOCK_PID.match(reason)
    return int(match.group(1)) if match else None


def session_in(entries: Iterable[str]) -> str | None:
    """환경 항목(`이름=값`)에서 세션 id. 이름은 글자 그대로 견주고, 값은 `local_<uuid>` 모양일
    때만 돌려준다. 찍은 `end-holders` 명령을 에이전트가 셸에 그대로 친다."""
    for entry in entries:
        key, separator, value = entry.partition("=")
        if separator and key == SESSION_ENV:
            return value if _SESSION_ID.fullmatch(value) else None
    return None


def sessions_of(
    holders: Sequence[Holder] | None, session_of: Callable[[int], str | None]
) -> dict[int, str]:
    """쥔 프로세스마다 환경의 세션 id. 읽지 못한 pid 는 넣지 않는다."""
    found: dict[int, str] = {}
    for holder in holders or ():
        session = session_of(holder.pid)
        if session is not None:
            found[holder.pid] = session
    return found


def parse_merged(text: str) -> dict[str, frozenset[str]]:
    """`gh pr list --json headRefName,headRefOid` 의 출력. 모양이 어긋나면 ValueError."""
    parsed: Json = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("배열이 아니다")
    heads: dict[str, set[str]] = {}
    for row in parsed:
        if not isinstance(row, dict):
            raise ValueError("객체가 아닌 항목이 있다")
        name = row.get("headRefName")
        oid = row.get("headRefOid")
        if not isinstance(name, str) or not isinstance(oid, str):
            raise ValueError("headRefName 이나 headRefOid 가 문자열이 아니다")
        heads.setdefault(name, set()).add(oid)
    return {name: frozenset(oids) for name, oids in heads.items()}


def tasklist_has(output: str, pid: int) -> bool:
    """`tasklist /FO CSV /NH` 의 출력에 그 pid 의 줄이 있는지. 둘째 칸이 pid 다."""
    return any(len(row) >= 2 and row[1] == str(pid) for row in csv.reader(output.splitlines()))


def unrecreatable(ignored: Sequence[str], *, settings_same: bool) -> list[str]:
    """`fold_ignored` 로 접은 `!!` 항목 중 다시 만들 수 없는 것. 디렉터리는 `/` 로 끝난다.
    `RECREATABLE_PATHS` 는 폴더와 파일을 끝의 `/` 로 가르므로 같은 이름의 다른 종류는 맞지
    않는다."""
    kept: list[str] = []
    for entry in ignored:
        name = entry.rstrip("/").rsplit("/", 1)[-1]
        if entry.endswith("/"):
            if name in RECREATABLE_DIRS or entry in RECREATABLE_PATHS:
                continue
        elif (
            entry in RECREATABLE_PATHS
            or name in RECREATABLE_FILES
            or name.endswith(RECREATABLE_SUFFIXES)
            or (entry == SETTINGS and settings_same)
        ):
            continue
        kept.append(entry)
    return kept


def fold_ignored(
    entries: Sequence[str], is_link: Callable[[str], bool], holds_tracked: Callable[[str], bool]
) -> tuple[str, ...]:
    """`status --ignored=matching` 의 `!!` 항목을 가장 바깥의 조상 가운데 링크(심볼릭 링크, 정션)
    이거나 다시 만들 수 있는 폴더(`_recreatable_dir`) 인 것으로 접는다. 추적 파일이 든 조상은 링크가
    아니면 건너뛴다. 두 판정은 워크트리 기준의 상대 경로를 받는다. 접은 자리는 처음 나온 차례로 한
    번만 든다.

    안쪽 `.gitignore` 로만 무시되는 폴더는 `matching` 이 그 안을 하나씩 찍는다. Grimp 는
    `.grimp_cache/` 안에 `*` 줄이 든 `.gitignore` 를 둔다(셀프 리뷰 명세 축). 하나씩 옮기다 막히면
    먼저 옮긴 그 `.gitignore` 가 빠져 남은 것이 미추적이 되므로 폴더째 접는다. 윈도의 git 2.32 는
    정션을 따라가 그 안도 하나씩 찍는다. 그대로 옮기면 링크 바깥의 파일이 옮겨지므로 링크째로
    접어, 링크는 제 이름으로 판정되고 옮기기는 링크만 옮긴다(둘 다 PR 직전 bug-perf-review 가
    임시 저장소로 재현했다). 추적 파일이 든 폴더로 접으면 옮기기가 추적 파일까지 옮긴다(PR 봇
    CodeRabbit). 그 폴더 안의 항목은 제 이름으로 판정되거나 더 안쪽 조상으로 접힌다. 추적 파일이 든
    링크는 `gather` 가 `tracked_links` 로 따로 모아 남긴다."""
    folded: dict[str, None] = {}
    for entry in entries:
        parts = entry.rstrip("/").split("/")
        place = entry
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            if holds_tracked(ancestor) and not is_link(ancestor):
                continue
            if _recreatable_dir(parts[depth - 1], ancestor) or is_link(ancestor):
                place = ancestor + "/"
                break
        folded[place] = None
    return tuple(folded)


def tracked_dirs(listing: str) -> frozenset[str]:
    """`ls-files -z` 의 출력에서 추적 파일이 든 폴더(워크트리 기준의 상대 경로). 견줄 쪽과 함께
    `os.path.normcase` 로 맞춘다. `normcase` 가 대소문자를 접는 윈도에서는 대소문자만 다른 자리도
    추적 파일이 든 폴더로 보아 접지 않는 쪽이다. 리눅스와 macOS 의 `normcase` 는 대소문자를 바꾸지
    않는다."""
    dirs: set[str] = set()
    for name in listing.split("\0"):
        parts = name.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            dirs.add(os.path.normcase("/".join(parts[:depth])))
    return frozenset(dirs)


def tracked_links(listing: str, is_link: Callable[[str], bool]) -> tuple[str, ...]:
    """`ls-files -z` 의 출력에서 추적 파일이 든 폴더 가운데 링크(심볼릭 링크, 정션)인 것을 끝에 `/`
    를 붙여 처음 나온 차례로 든다. 폴더마다 한 번만 보고 링크 안의 폴더는 보지 않는다. 윈도의 git
    은 추적 폴더를 갈음한 정션을 따라가 안의 파일이 체크아웃한 바이트와 같으면 바뀐 것으로 찍지
    않고, 안에 무시된 것도 미추적 파일도 없으면 `status` 에 아무것도 찍히지 않는다. 그때
    `git worktree remove` 가 정션을 따라가 링크 바깥의 파일을 지운다(PR 직전 bug-perf-review 의 대체
    리뷰가 임시 저장소로 재현했다). 그래서 무시된 항목이 아니라 추적 파일이 든 폴더에서 찾는다."""
    found: dict[str, None] = {}
    seen: set[str] = set()
    for name in listing.split("\0"):
        parts = name.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            folder = "/".join(parts[:depth])
            if folder in seen:
                if folder + "/" in found:
                    break
                continue
            seen.add(folder)
            if is_link(folder):
                found[folder + "/"] = None
                break
    return tuple(found)


def same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def same_branch(name: str | None, branch: str) -> bool:
    """`for-each-ref` 가 찍은 브랜치 이름을 세션 제목이나 워크트리 등록과 대소문자를 가리지 않고
    견준다. 윈도에서 낱개 참조의 폴더가 이미 다른 대소문자로 있으면 `for-each-ref` 는 그 폴더의
    이름으로 찍고, 제목과 등록은 친 그대로다(`chore/x` 옆에 만든 `Chore/Upper` 가 `chore/Upper` 로
    찍혔다. 테스트가 윈도에서 고정한다). 부르는 곳 셋 모두 맞으면 남기므로 잘못 맞아도 남기는
    쪽이다(대기열 286)."""
    return name is not None and name.casefold() == branch.casefold()


def _without_long_prefix(path: str) -> str:
    """`\\\\?\\UNC\\` 와 `\\\\?\\` 머리를 뗀다. 그 머리째 작업 디렉터리를 옮긴 프로세스는 PEB 에
    머리가 남는다(PR 직전 버그 리뷰가 손으로 봤다)."""
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[len("\\\\?\\UNC\\") :]
    return path.removeprefix("\\\\?\\")


def dos_path(device_path: str, drives: Mapping[str, str]) -> str | None:
    """`GetMappedFileNameW` 가 준 장치 경로를 드라이브 경로로. 드라이브 문자가 없는 장치(네트워크
    공유, 문자 없는 마운트 지점)면 None 이다. `drives` 는 장치 경로에서 드라이브(`C:`)로."""
    for device, drive in drives.items():
        if device_path.startswith(device + "\\"):
            return drive + device_path[len(device) :]
    return None


@functools.cache
def _normalized(path: str) -> str:
    """견주려고 정규화한 경로. 판정 한 번에 모듈 항목 수만큼의 경로를 워크트리마다 다시 견주므로
    기억해 둔다(PR 직전 버그·성능 리뷰)."""
    return os.path.normcase(os.path.normpath(_without_long_prefix(path)))


def is_within(child: str, parent: str) -> bool:
    """`child` 가 `parent` 자신이거나 그 아래인지. `x2` 는 `x` 의 아래가 아니다."""
    inner = _normalized(child)
    outer = _normalized(parent)
    return inner == outer or inner.startswith(outer.rstrip(os.sep) + os.sep)


def combine_holders(
    cwd: Sequence[Holder] | None, module: Sequence[Holder] | None
) -> list[Holder] | None:
    """작업 디렉터리로 쥔 것과 모듈을 올린 것. 둘 다 볼 수 없었을 때만 None 이다."""
    if cwd is None and module is None:
        return None
    return [*(cwd or ()), *(module or ())]


def describe_holders(
    holders: Sequence[Holder] | None, owners: Mapping[int, str] | None = None
) -> str:
    """남긴 이유에 붙일 쥔 프로세스. 못 찾은 것(빈 목록)과 볼 수 없는 것(None)을 가른다. `owners`
    는 pid 마다 환경의 세션 id 이고, 있으면 pid 옆에 적는다."""
    known = owners or {}
    if holders is None:
        return "쥔 프로세스를 찾지 못했다(이 OS 에서 볼 수 없거나 프로세스를 읽다 실패했다)"
    if not holders:
        # 한쪽 훑기만 볼 수 있었어도 빈 목록이 온다(리눅스는 모듈을 보지 않는다). 그래서 무엇을
        # 보았는지 단정하지 않고 이 도구가 대는 범위만 적는다
        return (
            "읽을 수 있는 프로세스에서 쥔 것을 찾지 못했다. 이 도구는 작업 디렉터리와 (윈도에서) "
            "올린 모듈만 대고, 읽지 못한 프로세스(다른 사용자, 높은 권한)와 그 안의 파일을 연 "
            "프로세스는 대지 못한다"
        )
    parts: list[str] = []
    for kind, label in _HOLDER_LABELS.items():
        names = ", ".join(
            f"{holder.image or '(이름 모름)'}(pid {holder.pid}{_session_note(known, holder.pid)})"
            for holder in holders
            if holder.kind == kind
        )
        if names:
            parts.append(f"{label}: {names}")
    return "; ".join(parts)


def _session_note(owners: Mapping[int, str], pid: int) -> str:
    session = owners.get(pid)
    return "" if session is None else f", 세션 {session}"


# --- 판정 ---------------------------------------------------------------------------------------


def judge(
    wt: Worktree,
    facts: Facts,
    merged: Mapping[str, frozenset[str]],
    running: Sequence[str],
    alive: Callable[[int], bool],
    holders: Sequence[Holder] | None,
    *,
    owners: Mapping[int, str] | None = None,
    idle: Collection[str] = (),
) -> Verdict:
    """워크트리 하나의 판정. 순서와 근거는 모듈 독스트링. `holders` 는 그 폴더를 작업 디렉터리로
    쥔 프로세스이고, 볼 수 없었으면 None 이다. `owners` 는 쥔 프로세스마다 환경의 세션 id 이고,
    `idle` 은 부르는 쪽이 쉰다고 넘긴 세션이다(부른 세션은 빼고 넘긴다)."""

    def verdict(action: Action, reason: str) -> Verdict:
        return Verdict(action, wt.path, reason, wt.branch, wt.head)

    if wt.prunable or not facts.exists:
        if facts.exists and facts.has_git:
            return verdict("human", "등록이 prunable 인데 폴더에 .git 이 있다. 사람이 본다")
        if wt.branch is None and not facts.contained:
            # 등록이 그 커밋의 마지막 참조일 수 있다. 걷으면 커밋이 매달린다(명세 축 리뷰가 폴더
            # 없는 경우를, PR 직전 버그 리뷰가 지우다 만 폴더의 경우를 임시 저장소에서 재현했다,
            # 일지 2026-10-15-06)
            reason = "분리 HEAD 이고 그 커밋이 origin/main 에 없다. 등록을 걷지 않는다"
            return verdict("human", reason)
        if facts.exists:
            # 지우다 만 폴더다. 부르는 쪽이 등록 없는 폴더의 판정으로 내용을 가른다
            return verdict("delete", "등록이 prunable 이고 폴더에 .git 이 없다")
        if facts.aside:
            reason = "폴더가 옆 이름(.tidy-probe)에 남았다. 되돌린다 줄의 restore 가 되돌린다"
            return verdict("keep", reason)
        if wt.locked is not None:
            return verdict("human", f"폴더가 없는데 등록이 잠겨 있다: {wt.locked or '(사유 없음)'}")
        return verdict("delete", "폴더가 없고 등록만 남았다. remove 가 등록을 걷는다")
    if facts.toplevel is None or not same_path(facts.toplevel, wt.path):
        return verdict("human", f"그 폴더의 git 이 다른 저장소({facts.toplevel})를 읽는다")
    if facts.app_marker:
        return verdict("keep", f"앱의 표지({APP_MARKER})가 있다. 앱의 정리에 맡긴다")
    if wt.head is None:
        return verdict("human", "HEAD 를 읽지 못했다")
    if wt.branch is None:
        if not facts.contained:
            return verdict("human", "분리 HEAD 이고 그 커밋이 origin/main 에 없다")
    else:
        heads = merged.get(wt.branch)
        if not heads:
            return verdict("keep", "병합된 PR 이 없다")
        if wt.head not in heads and not facts.behind:
            return verdict("human", "병합된 PR 의 머리와 브랜치 끝이 다르다")
    if facts.status:
        return verdict("keep", "바뀐 파일이 있다")
    if facts.status_err:
        return verdict("keep", f"git 이 경고를 냈다: {facts.status_err.strip()[:120]}")
    if facts.tracked_links:
        places = ", ".join(facts.tracked_links[:5])
        return verdict("keep", f"추적 폴더를 링크가 갈음했다: {places}")
    extra = unrecreatable(facts.ignored, settings_same=facts.settings_same)
    if extra:
        return verdict("keep", f"다시 만들 수 없는 무시된 항목: {', '.join(extra[:5])}")
    if wt.branch in running:
        return verdict("keep", _RUNNING_REASON)
    pid = None if wt.locked is None else lock_pid(wt.locked)
    if wt.locked is not None and pid is None:
        return verdict("human", f"잠금 사유에 pid 가 없다: {wt.locked or '(사유 없음)'}")
    if pid is not None and alive(pid) and not _lock_ends(pid, holders, owners, idle):
        return verdict("keep", f"잠금 pid {pid} 가 살아 있다. 그 세션: {wt.locked}")
    if holders:
        described = describe_holders(holders, owners)
        sessions = idle_sessions(holders, owners or {}, idle)
        if sessions:
            reason = f"쉬는 세션의 프로세스만 쥐었다. {described}. 끝내면 지울 수 있다"
            return replace(verdict("end", reason), sessions=sessions)
        return verdict("keep", f"{described}. 그 프로세스가 끝나야 지운다")
    if wt.branch is None:
        note = "분리 HEAD 이고 그 커밋이 origin/main 에 있다"
    else:
        note = _BEHIND_REASON if facts.behind else ""
    if pid is None:
        return verdict("delete", note)
    dead = f"잠금 pid {pid} 는 죽었다. remove 가 풀고 지운다"
    return Verdict("delete", wt.path, dead, wt.branch, wt.head, unlock=True)


def _lock_ends(
    pid: int,
    holders: Sequence[Holder] | None,
    owners: Mapping[int, str] | None,
    idle: Collection[str],
) -> bool:
    """산 잠금 pid 를 쥔 프로세스로 함께 끝낼 수 있는가. 부르는 쪽이 그 pid 를 쥔 것에 넣었고
    (`with_lock`) 그 세션이 쉰다고 받은 세션일 때만이다. 넣지 않았는데 지나가면 판정이 `지운다` 로
    흘러 산 잠금을 푼다."""
    return any(holder.pid == pid for holder in holders or ()) and (owners or {}).get(pid) in idle


def with_lock(
    holders: Sequence[Holder] | None, wt: Worktree, alive: Callable[[int], bool]
) -> list[Holder] | None:
    """쥔 프로세스에 산 잠금 pid 를 더한다(이미 들었으면 그대로). 잠금 pid 는 그 워크트리를 연
    세션의 `claude.exe` 이고, 그 세션이 쉬면 함께 끝낸다. 쥔 것을 볼 수 없었으면(None) 더하지
    않는다."""
    if holders is None:
        return None
    pid = None if wt.locked is None else lock_pid(wt.locked)
    if pid is None or not alive(pid) or any(holder.pid == pid for holder in holders):
        return list(holders)
    return [*holders, Holder(pid, "", "lock")]


def idle_sessions(
    holders: Sequence[Holder], owners: Mapping[int, str], idle: Collection[str]
) -> tuple[str, ...]:
    """쥔 프로세스가 모두 쉬는 세션의 것이면 그 세션들(정렬). 하나라도 세션을 모르거나 쉬는 세션이
    아니면 빈 튜플이다."""
    sessions = {owners.get(holder.pid) for holder in holders}
    if not holders or None in sessions:
        return ()
    known = {session for session in sessions if session is not None}
    return tuple(sorted(known)) if known <= set(idle) else ()


def hold_for_strangers(
    verdicts: Sequence[Verdict], running: Sequence[str], checked_out: set[str]
) -> list[Verdict]:
    """제목이 체크아웃된 어느 브랜치와도 맞지 않는 실행 중 세션이 있으면 지울 것을 넘긴다.
    부르는 쪽(`_judge_all`)은 프로세스의 작업 디렉터리를 읽었을 때 이 함수를 부르지 않는다.
    세션의 `claude.exe` 가 그 워크트리를 작업 디렉터리로 쥐어 판정 3이 이름으로 남긴다."""
    strangers = [title for title in running if title not in checked_out]
    if not strangers:
        return list(verdicts)
    reason = f"제목이 체크아웃된 어느 브랜치와도 맞지 않는 세션이 돈다: {', '.join(strangers)}"
    return [
        replace(v, action="hold", reason=reason) if v.action == "delete" else v for v in verdicts
    ]


def judge_branch(
    branch: str,
    tip: str,
    merged: Mapping[str, frozenset[str]],
    running: Sequence[str],
    *,
    contained: bool = False,
    behind: bool = False,
    fresh: bool = False,
) -> Verdict:
    """체크아웃되지 않은 로컬 브랜치의 판정. 판정 1이 지울 것으로 낸 뒤에 판정 3의 제목을 본다.
    `running` 은 실행 중 세션의 제목과 브랜치이고, 대소문자를 가리지 않고 견준다(`same_branch`,
    대기열 286)."""
    verdict = _judge_branch_merged(
        branch, tip, merged, contained=contained, behind=behind, fresh=fresh
    )
    if verdict.action == "delete" and any(same_branch(title, branch) for title in running):
        return replace(verdict, action="keep", reason=_RUNNING_REASON)
    return verdict


def _judge_branch_merged(
    branch: str,
    tip: str,
    merged: Mapping[str, frozenset[str]],
    *,
    contained: bool,
    behind: bool,
    fresh: bool,
) -> Verdict:
    """판정 1. `contained` 는 브랜치 끝이 `origin/main` 에서 닿는다는 뜻이다. 병합된 PR 이 없어도
    그러면 지운다. 잃는 것은 이름뿐이다. 다만 `fresh`(reflog 의 마지막 기록이 `FRESH_SECONDS`
    안이다)면 막 딴 브랜치라 남긴다(대기열 440). `behind` 는 끝이 병합된 PR 머리의 조상이라는
    뜻이다. 병합된 PR 로 지우는 길은 `fresh` 를 보지 않는다."""
    if branch in PROTECTED_BRANCHES:
        return Verdict("keep", branch, "지우지 않는 브랜치다", branch, tip)
    heads = merged.get(branch)
    if not heads:
        if contained and fresh:
            return Verdict("keep", branch, _FRESH_REASON, branch, tip)
        if contained:
            return Verdict("delete", branch, "커밋이 모두 origin/main 에 있다", branch, tip)
        reason = "병합된 PR 이 없고 origin/main 에 없는 커밋이 있다"
        return Verdict("keep", branch, reason, branch, tip)
    if tip not in heads:
        if behind:
            return Verdict("delete", branch, _BEHIND_REASON, branch, tip)
        return Verdict("human", branch, "병합된 PR 의 머리와 브랜치 끝이 다르다", branch, tip)
    return Verdict("delete", branch, "", branch, tip)


@dataclass(frozen=True)
class StrayFacts:
    """등록 없는 폴더의 판정 재료. `.git` 이 있으면 안을 읽지 않아 나머지는 빈 값이다.
    `error` 는 읽다 막힌 이유(없으면 ""), `links` 와 `uncommitted` 는 폴더 안의 상대 경로다."""

    has_git: bool
    error: str
    links: tuple[str, ...]
    uncommitted: tuple[str, ...]


def judge_stray(
    path: str,
    facts: StrayFacts,
    holders: Sequence[Holder] | None,
    orphan_home: str | None = None,
) -> Verdict:
    """등록 없는 폴더 하나의 판정. 순서와 근거는 모듈 독스트링의 "등록 없는 폴더". `orphan_home` 은
    이 폴더가 점유 탐침의 옆 이름일 때 폴더를 잃은 채 남은 원래 이름의 등록 경로다."""

    def verdict(action: Action, reason: str) -> Verdict:
        return Verdict(action, path, reason)

    if facts.has_git:
        if orphan_home is not None:
            reason = f"점유 탐침이 옆 이름에 남긴 폴더이고 {orphan_home} 의 등록이 폴더를 잃었다"
            return verdict("restore", reason)
        reason = "등록 없는 폴더인데 .git 이 있다. 어느 등록이 이 폴더를 잃었을 수 있다"
        return verdict("human", reason)
    if facts.error:
        return verdict("keep", f"등록 없는 폴더를 읽다 막혔다: {facts.error}")
    if facts.links:
        return verdict("keep", f"등록 없는 폴더에 링크가 있다: {', '.join(facts.links[:5])}")
    if facts.uncommitted:
        shown = ", ".join(facts.uncommitted[:5])
        count = len(facts.uncommitted)
        return verdict("keep", f"등록 없는 폴더에 커밋에 없는 파일이 {count}개 있다: {shown}")
    if holders:
        return verdict("keep", f"{describe_holders(holders)}. 그 프로세스가 끝나야 지운다")
    return verdict("delete", "등록 없는 폴더")


def looks_text(data: bytes) -> bool:
    """git 이 줄 끝을 바꾸는 텍스트로 볼 내용인지. NUL, 홀로 쓰인 CR, 인쇄 문자 128개당 비인쇄 문자
    하나를 넘는 비율이면 바이너리다. CR·LF 는 어느 쪽에도 세지 않고, 끝의 `\\x1a` 하나도 어느
    쪽에도 세지 않는다. git 소스를 읽지 않고 알고 있던 규칙이라(어림) 테스트가 `git hash-object` 와
    견준다."""
    if b"\0" in data or data.count(b"\r") != data.count(b"\r\n"):
        return False
    counted = len(data) - len(data.translate(None, _NONPRINTABLE))
    printable = len(data) - counted - data.count(b"\r") - data.count(b"\n")
    nonprintable = counted - 1 if data.endswith(b"\x1a") else counted
    return (printable >> 7) >= nonprintable


def blob_ids(data: bytes) -> set[str]:
    """git 이 이 내용에 붙일 블롭 이름. `.gitattributes` 의 `* text=auto eol=lf` 라 git 이 텍스트로
    보는 내용은 CRLF 를 LF 로 바꾼 이름도 든다(`looks_text`)."""
    candidates = {data}
    if b"\r\n" in data and looks_text(data):
        candidates.add(data.replace(b"\r\n", b"\n"))
    return {
        hashlib.sha1(b"blob %d\0" % len(body) + body, usedforsecurity=False).hexdigest()
        for body in candidates
    }


# --- 배관 ---------------------------------------------------------------------------------------


def _checked(git: GitRunner, args: Sequence[str], cwd: Path) -> str:
    result = git(args, cwd)
    if result.returncode != 0:
        raise ToolError(f"git {' '.join(args)} 가 {result.returncode} 로 끝났다: {result.stderr}")
    return result.stdout


def _same_settings(left: Path, right: Path) -> bool:
    try:
        return settings_equivalent(left.read_bytes(), right.read_bytes())
    except OSError:
        return False


def settings_equivalent(left: bytes, right: bytes) -> bool:
    """두 local 설정이 같은가. 바이트가 같거나, 둘 다 JSON 객체로 풀리고 `skillOverrides` 에서
    `WORKTREE_OVERRIDE_PREFIX` 로 시작하는 키를 뺀 나머지가 같으면 같다. 그 키는
    `tools/hook_worktree_skill_overrides.py` 가 주 체크아웃의 local 에 적고 다시 쓰는 것이라(대기열
    274), 워크트리를 만들 때 받은 사본은 그 키와 서식만 달라도 다시 만들 수 있다. 풀리지 않으면
    다르다고 본다(남기는 쪽)."""
    if left == right:
        return True
    try:
        first: Json = json.loads(left.decode("utf-8-sig"))
        second: Json = json.loads(right.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    return _without_worktree_overrides(first) == _without_worktree_overrides(second)


def _without_worktree_overrides(settings: dict[str, Json]) -> dict[str, Json]:
    overrides = settings.get(OVERRIDES)
    if not isinstance(overrides, dict):
        return settings
    kept: dict[str, Json] = {
        key: value
        for key, value in overrides.items()
        if not key.startswith(WORKTREE_OVERRIDE_PREFIX)
    }
    rest = {key: value for key, value in settings.items() if key != OVERRIDES}
    return {**rest, OVERRIDES: kept} if kept else rest


def _misplaced(*, exists: bool, toplevel: str | None) -> Facts:
    """자리가 어긋나 status 를 읽지 않은 재료. 그 폴더의 git 은 루트에 닿을 수 있다."""
    return Facts(
        exists=exists, toplevel=toplevel, status="", status_err="", ignored=(), settings_same=False
    )


def contains(root: Path, commit: str, git: GitRunner) -> bool:
    """`commit` 이 `origin/main` 에서 닿는지. `origin/main` 이 없으면 닿지 않는 것으로 본다."""
    return git(["merge-base", "--is-ancestor", commit, "origin/main"], root).returncode == 0


def behind_merged(root: Path, tip: str, heads: Collection[str] | None, git: GitRunner) -> bool:
    """`tip` 이 `heads`(이름이 같은 병합된 PR 의 머리) 가운데 하나의 조상인지. 끝이 머리와 같으면
    읽지 않고 False 다. 머리 커밋이 이 저장소에 없으면(받아 오지 않았다) 닿지 않는 것으로 본다."""
    if not heads or tip in heads:
        return False
    return any(
        git(["merge-base", "--is-ancestor", tip, head], root).returncode == 0
        for head in sorted(heads)
    )


def touched_at(printed: str) -> int | None:
    """`git log -g -n 1 --format=%gd --date=unix` 의 출력(`<브랜치>@{<유닉스 초>}`)에서 시각을
    읽는다. git 은 브랜치 이름에 `@{` 를 허락하지 않아 `@{` 는 선택자의 것뿐이다. 기록이 없거나
    모양이 어긋나면 None 이다."""
    _, mark, rest = printed.strip().rpartition("@{")
    seconds = rest.removesuffix("}")
    if not mark or seconds == rest or not seconds.isdigit():
        return None
    return int(seconds)


def branch_touched(root: Path, branch: str, git: GitRunner) -> int | None:
    """브랜치 reflog 의 마지막 기록 시각(유닉스 초). 따기, 이름 바꾸기(`git branch -m`), 끝 옮기기가
    모두 기록을 남긴다. 기록이 없거나 읽지 못하면 None 이다."""
    args = ["log", "-g", "-n", "1", "--format=%gd", "--date=unix", f"refs/heads/{branch}", "--"]
    found = git(args, root)
    return touched_at(found.stdout) if found.returncode == 0 else None


def is_fresh(touched: int | None, now: float) -> bool:
    """`touched` 가 `FRESH_SECONDS` 안이거나 앞날(시계가 어긋난 PC)이면 막 딴 브랜치다. 기록이
    없으면 막 딴 것인지 모른다(못 보는 것)."""
    return touched is not None and now - touched < FRESH_SECONDS


def _has_app_marker(path: Path, git: GitRunner) -> bool:
    """그 워크트리의 git 디렉터리(`.git/worktrees/<이름>/`)에 앱의 표지가 있는지."""
    found = git(["rev-parse", "--absolute-git-dir"], path)
    if found.returncode != 0:
        return False
    return (Path(found.stdout.strip()) / APP_MARKER).exists()


def gather(root: Path, wt: Worktree, git: GitRunner, merged: Mapping[str, frozenset[str]]) -> Facts:
    path = Path(wt.path)
    # 분리 HEAD 는 폴더가 없어도 본다. 등록을 걷기 전에 그 커밋이 origin/main 에 있는지 알아야 한다
    contained = wt.branch is None and wt.head is not None and contains(root, wt.head, git)
    if not path.is_dir():
        aside = os.path.lexists(path.with_name(path.name + PROBE_SUFFIX))
        missing = _misplaced(exists=False, toplevel=None)
        return replace(missing, aside=aside, contained=contained)
    if wt.prunable:
        dead = _misplaced(exists=True, toplevel=None)
        return replace(dead, has_git=(path / ".git").exists(), contained=contained)
    top = git(["rev-parse", "--show-toplevel"], path)
    toplevel = top.stdout.strip() if top.returncode == 0 else None
    if toplevel is None or not same_path(toplevel, wt.path):
        return _misplaced(exists=True, toplevel=toplevel)
    status = git(["status", "--porcelain", "-z", "--untracked-files=all"], path)
    status_err = status.stderr or ("" if status.returncode == 0 else f"exit {status.returncode}")
    # 기본(`traditional`)은 무시된 것만 든 미추적 폴더를 그 폴더로 접어 찍는다(대기열 464)
    listed = git(["status", "--porcelain", "-z", "--ignored=matching"], path)
    if listed.returncode != 0 and not status_err:
        status_err = listed.stderr or f"exit {listed.returncode}"
    tracked = git(["ls-files", "-z"], path)
    if tracked.returncode != 0 and not status_err:
        status_err = f"ls-files: {tracked.stderr or f'exit {tracked.returncode}'}"
    found = [item[3:] for item in listed.stdout.split("\0") if item.startswith("!! ")]
    holding = tracked_dirs(tracked.stdout)

    def is_link(relative: str) -> bool:
        # MAX_PATH 를 넘는 링크는 `\\?\` 없이 물으면 링크가 아닌 것으로 보인다(셀프 리뷰 명세 축)
        return _is_link(Path(long_path(path / relative)))

    def holds_tracked(relative: str) -> bool:
        return os.path.normcase(relative) in holding

    ignored = fold_ignored(found, is_link, holds_tracked)
    links = tracked_links(tracked.stdout, is_link)
    settings_same = _same_settings(root / SETTINGS, path / SETTINGS)
    behind = (
        wt.branch is not None
        and wt.head is not None
        and behind_merged(root, wt.head, merged.get(wt.branch), git)
    )
    return Facts(
        exists=True,
        toplevel=toplevel,
        status=status.stdout,
        status_err=status_err,
        ignored=ignored,
        settings_same=settings_same,
        contained=contained,
        behind=behind,
        app_marker=_has_app_marker(path, git),
        tracked_links=links,
    )


def reachable_objects(root: Path, git: GitRunner) -> frozenset[str]:
    """참조(브랜치, 원격, 태그, stash)에서 닿는 객체의 이름. 리플로그에만 남은 것과 매달린 객체는
    빼 둔다. 둘 다 시간이 지나면 git 이 지운다."""
    listed = _checked(git, ["rev-list", "--all", "--objects"], root)
    return frozenset(line.split(" ", 1)[0] for line in listed.splitlines() if line)


def _recreatable_dir(name: str, relative: str) -> bool:
    return name in RECREATABLE_DIRS or relative + "/" in RECREATABLE_PATHS


def _walk_stray(folder: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """((파일의 상대 경로, 그 파일을 열 경로), 링크의 상대 경로). 다시 만들 수 있는 폴더는 링크여도
    들어가지 않고 건너뛴다. 링크(심볼릭 링크, 정션)는 따라가지 않는다. 읽다 막히면 OSError.

    여는 경로는 `scandir` 가 준 그대로 들고 다닌다. 상대 경로를 다시 이어 붙여 정규화하면 끝에
    점이 붙은 이름이 점 없는 다른 파일로 읽힌다(`long_path`).
    """
    files: list[tuple[str, str]] = []
    links: list[str] = []
    pending = [("", long_path(folder))]
    while pending:
        relative, opened = pending.pop()
        with os.scandir(opened) as entries:
            for entry in entries:
                child = f"{relative}/{entry.name}" if relative else entry.name
                linked = entry.is_symlink() or entry.is_junction()
                directory = linked or entry.is_dir(follow_symlinks=False)
                if directory and _recreatable_dir(entry.name, child):
                    continue
                if linked:
                    links.append(child)
                elif directory:
                    pending.append((child, entry.path))
                else:
                    files.append((child, entry.path))
    return sorted(files), sorted(links)


def gather_stray(root: Path, folder: Path, reachable: Callable[[], frozenset[str]]) -> StrayFacts:
    """등록 없는 폴더의 재료. git 은 그 폴더에서 부르지 않는다(`.git` 이 없어 루트에 닿는다).
    `reachable` 은 확인할 파일이 있을 때만 부른다."""
    if os.path.lexists(long_path(folder / ".git")):
        return StrayFacts(has_git=True, error="", links=(), uncommitted=())
    try:
        files, links = _walk_stray(folder)
        named = [
            (relative, file_blob_ids(opened))
            for relative, opened in files
            if not _recreatable_file(root, folder, relative)
        ]
    except OSError as error:
        return StrayFacts(has_git=False, error=str(error), links=(), uncommitted=())
    known = reachable() if named else frozenset[str]()
    uncommitted = tuple(relative for relative, ids in named if ids.isdisjoint(known))
    return StrayFacts(has_git=False, error="", links=tuple(links), uncommitted=uncommitted)


def _recreatable_file(root: Path, folder: Path, relative: str) -> bool:
    """다시 만들 수 있는 파일(`RECREATABLE_FILES` 의 이름, `RECREATABLE_PATHS` 의 파일 자리, 루트와
    같은 설정 파일. 같음은 `settings_equivalent`). `RECREATABLE_PATHS` 의 파일 자리는 워크트리
    판정(`unrecreatable`)과 같이 본다. 덤프(`RECREATABLE_SUFFIXES`)는 워크트리 판정만 본다."""
    if relative.rsplit("/", 1)[-1] in RECREATABLE_FILES or relative in RECREATABLE_PATHS:
        return True
    return relative == SETTINGS and _same_settings(root / SETTINGS, folder / SETTINGS)


def file_blob_ids(path: str) -> set[str]:
    """파일 하나의 `blob_ids`. `WHOLE_READ_LIMIT` 를 넘는 파일은 통째로 읽지 않고 덩이로 그대로의
    이름만 셈한다. 줄 끝을 바꾼 이름이 빠져, git 이 텍스트로 넣은 큰 파일은 남는 쪽이다."""
    size = os.stat(path).st_size
    with open(path, "rb") as handle:
        if size <= WHOLE_READ_LIMIT:
            return blob_ids(handle.read())
        digest = hashlib.sha1(b"blob %d\0" % size, usedforsecurity=False)
        for chunk in iter(functools.partial(handle.read, 1 << 20), b""):
            digest.update(chunk)
    return {digest.hexdigest()}


def _place(cwd: Path, git: GitRunner) -> tuple[Path, list[Worktree]]:
    """주 체크아웃의 루트와 워크트리 목록. 주 체크아웃이 아니면 ValueError."""
    top = git(["rev-parse", "--show-toplevel"], cwd)
    if top.returncode != 0:
        raise ValueError(f"git 저장소가 아니다: {top.stderr.strip()}")
    listing = parse_worktrees(_checked(git, ["worktree", "list", "--porcelain"], cwd))
    if not listing or not same_path(top.stdout.strip(), listing[0].path):
        raise ValueError("이 폴더는 워크트리다. 주 체크아웃 세션에서 돈다")
    prefix = _checked(git, ["rev-parse", "--show-prefix"], cwd).strip()
    if prefix.startswith(WORKTREES_DIR + "/"):
        raise ValueError(f"지우다 만 워크트리 폴더 안이다({prefix}). git 이 루트에 닿는다")
    return Path(listing[0].path), listing


def _unregistered(root: Path, listing: Sequence[Worktree]) -> list[Path]:
    """`.claude/worktrees/` 바로 아래인데 등록이 없는 폴더와 폴더를 가리키는 링크."""
    holder = root / WORKTREES_DIR
    if not holder.is_dir():
        return []
    trash = root / TRASH_DIR
    return sorted(
        path
        for path in holder.iterdir()
        if path.is_dir()
        and not same_path(str(path), str(trash))
        and not any(same_path(str(path), wt.path) for wt in listing)
    )


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _strays(root: Path, listing: Sequence[Worktree]) -> list[Path]:
    """등록 없는 폴더. 링크는 안을 읽지 않으려고 뺀다(`judge` 는 따로 넘긴다)."""
    return [path for path in _unregistered(root, listing) if not _is_link(path)]


def _orphan_home(stray: Path, listing: Sequence[Worktree]) -> str | None:
    """`stray` 가 점유 탐침의 옆 이름이고 원래 이름의 등록이 폴더를 잃은 채 남았으면 그 경로."""
    if not stray.name.endswith(PROBE_SUFFIX):
        return None
    home = stray.with_name(stray.name.removesuffix(PROBE_SUFFIX))
    registered = any(same_path(str(home), wt.path) for wt in listing)
    return home.as_posix() if registered and not os.path.lexists(home) else None


def _render_worktree(verdict: Verdict) -> str:
    if verdict.action == "end":
        command = f'{COMMAND} end-holders "{verdict.path}" {" ".join(verdict.sessions)}'
        return _render(verdict, "", command)
    branch = DETACHED if verdict.branch is None else verdict.branch
    command = f'{COMMAND} remove "{verdict.path}" {branch} {verdict.head}'
    return _render(verdict, "", command)


def _render_branch(verdict: Verdict) -> str:
    command = f"{COMMAND} remove-branch {verdict.branch} {verdict.head}"
    return _render(verdict, "브랜치를 ", command)


def _render_stray(verdict: Verdict) -> str:
    if verdict.action == "restore":
        return _render(verdict, "", f'{COMMAND} restore "{verdict.path}"')
    return _render(verdict, "", f'{COMMAND} remove-stray "{verdict.path}"')


def _render(verdict: Verdict, prefix: str, command: str) -> str:
    """판정 한 줄. `prefix` 는 라벨 앞에 붙는 말이다(브랜치 줄은 `브랜치를 `)."""
    label = prefix + _ACTIONS[verdict.action]
    names = (verdict.path, verdict.branch or "", verdict.head or "", *verdict.sessions)
    commanded = verdict.action in ("delete", "hold", "restore", "end")
    if commanded and any(map(_SHELL_UNSAFE.search, names)):
        hand_off = prefix + "넘긴다"
        return f"{hand_off} {verdict.path} — 셸이 풀 수 있는 글자가 든 이름이라 명령을 찍지 않는다"
    if verdict.action == "hold":
        return f"{label} {verdict.path} — {verdict.reason}. 승인하면 → {command}"
    if verdict.action == "end":
        return f"{label} {verdict.path} — {verdict.reason} → {command}"
    if verdict.action not in ("delete", "restore"):
        return f"{label} {verdict.path} — {verdict.reason}"
    note = f" ({verdict.reason})" if verdict.reason else ""
    return f"{label} {verdict.path}{note} → {command}"


def _reachable(root: Path, git: GitRunner) -> Callable[[], frozenset[str]]:
    """참조에서 닿는 객체를 처음 부를 때 한 번만 읽는다."""
    return functools.cache(lambda: reachable_objects(root, git))


def _fresh(
    root: Path,
    branch: str,
    merged: Mapping[str, frozenset[str]],
    git: GitRunner,
    now: float,
    *,
    contained: bool,
) -> bool:
    """판정 1의 `fresh`. 그 값을 보는 길(병합된 PR 이 없고 끝이 `origin/main` 에 있다)에서만 reflog
    를 읽는다. `judge` 와 `remove-branch` 가 같이 쓴다."""
    if merged.get(branch) or not contained:
        return False
    return is_fresh(branch_touched(root, branch, git), now)


def _contained_branches(root: Path, git: GitRunner) -> frozenset[str]:
    """끝이 `origin/main` 에서 닿는 로컬 브랜치. `origin/main` 이 없으면 빈 집합이다."""
    args = ["for-each-ref", "--merged", "origin/main", "--format=%(refname:short)", "refs/heads"]
    listed = git(args, root)
    if listed.returncode != 0:
        return frozenset()
    return frozenset(line for line in listed.stdout.splitlines() if line)


def _judge_all(
    root: Path,
    listing: list[Worktree],
    running: Sequence[str],
    idle: Collection[str],
    ops: Ops,
) -> int:
    """`idle` 은 부르는 쪽이 쉰다고 넘긴 세션에서 이 도구를 부른 세션을 뺀 것이다."""
    merged = ops.merged(root)
    others = [wt for wt in listing[1:] if not wt.bare]
    processes = ops.processes()
    reachable = _reachable(root, ops.git)
    # 모듈 훑기는 한 번에 1초 안팎이라 처음 필요할 때 한 번만 한다(등록 없는 폴더와 휴지통)
    modules = functools.cache(ops.modules)
    verdicts: list[Verdict] = []
    for wt in others:
        facts = gather(root, wt, ops.git, merged)
        holders = with_lock(holders_in(processes, wt.path), wt, ops.pid_alive)
        owners = sessions_of(holders, ops.session_of)
        verdict = judge(
            wt, facts, merged, running, ops.pid_alive, holders, owners=owners, idle=idle
        )
        if _dead(wt, facts):
            # 지우다 만 폴더. 내용은 등록 없는 폴더의 판정으로 가르고, 명령은 워크트리의 것이다
            holders = holders_from(processes, modules(), wt.path)
            inner = judge_stray(wt.path, gather_stray(root, Path(wt.path), reachable), holders)
            if inner.action != "delete":
                verdict = replace(inner, branch=wt.branch, head=wt.head)
        verdicts.append(verdict)
    checked_out = {wt.branch for wt in listing if wt.branch is not None}
    # 빈 목록은 읽지 못한 것으로 본다. 훑기가 됐으면 이 도구 자신의 파이썬이 들어 비지 않는다
    # (윈도의 `K32EnumProcesses` 실패와 모든 `OpenProcess` 실패가 빈 목록을 돌려준다, PR #243
    # CodeRabbit)
    held = verdicts if processes else hold_for_strangers(verdicts, running, checked_out)
    for verdict in held:
        print(_render_worktree(verdict))
    for place in _unregistered(root, listing):
        path = place.as_posix()
        if _is_link(place):
            print(f"넘긴다 {path} — 등록 없는 자리가 링크다. 안을 읽지 않는다")
            continue
        facts = gather_stray(root, place, reachable)
        holders = holders_from(processes, modules(), path)
        print(_render_stray(judge_stray(path, facts, holders, _orphan_home(place, listing))))
    refs = _checked(
        ops.git, ["for-each-ref", "refs/heads", "--format=%(refname:short) %(objectname)"], root
    )
    contained = _contained_branches(root, ops.git)
    now = ops.now()
    for line in refs.splitlines():
        branch, _, tip = line.partition(" ")
        if branch and not any(same_branch(name, branch) for name in checked_out):
            inside = branch in contained
            behind = behind_merged(root, tip, merged.get(branch), ops.git)
            fresh = _fresh(root, branch, merged, ops.git, now, contained=inside)
            verdict = judge_branch(
                branch, tip, merged, running, contained=inside, behind=behind, fresh=fresh
            )
            print(_render_branch(verdict))
    if trash_dir(root) is None:
        print(_trash_refused(root))
    leftovers = _trash_entries(root)
    for entry in leftovers:
        holders = combine_holders(
            holders_from(processes, modules(), str(entry)),
            holders_from(processes, modules(), origin_of(root, entry)),
        )
        print(f"휴지통에 남았다 {entry.as_posix()} — {describe_holders(holders)}")
    if leftovers:
        print(f"휴지통을 비운다 → {COMMAND} empty-trash")
    return 0


def trash_dir(root: Path) -> Path | None:
    """휴지통 자리. 그 자리가 링크(심볼릭 링크, 정션)거나 폴더가 아닌 것이면 None. 링크 너머를
    휴지통으로 읽으면 `empty-trash` 가 링크 너머의 내용을 지운다(PR 직전 보안 리뷰가 정션으로
    재현했다, 일지 2026-10-15-06). 등록 없는 폴더의 링크 처리와 같다."""
    trash = root / TRASH_DIR
    if _is_link(trash) or (os.path.lexists(trash) and not trash.is_dir()):
        return None
    return trash


def _trash_entries(root: Path) -> list[Path]:
    """휴지통 바로 아래의 항목. 이전 `remove` 가 옮겨 두고 지우지 못한 것이다. 자리가 링크면
    읽지 않는다(빈 목록)."""
    trash = trash_dir(root)
    if trash is None or not trash.is_dir():
        return []
    return sorted(trash.iterdir())


TRASH_REFUSED = "휴지통 자리가 링크거나 폴더가 아니다. 안을 읽지 않는다"


def _trash_refused(root: Path) -> str:
    return f"넘긴다 {(root / TRASH_DIR).as_posix()} — {TRASH_REFUSED}"


def flatten(relative: str) -> str:
    """워크트리 안 상대 경로를 휴지통 자리 이름의 한 토막으로. `%` 를 `%25` 로, `/` 를 `%2F` 로 바꿔
    `unflatten` 이 되돌릴 수 있다(`__pycache__` 처럼 `_` 가 든 이름이 `__` 치환과 섞이지 않는다)."""
    return relative.rstrip("/").replace("%", "%25").replace("/", "%2F")


def unflatten(flat: str) -> str:
    return flat.replace("%2F", "/").replace("%25", "%")


def trash_slot(root: Path, name: str, entry: str) -> Path:
    """`entry`(워크트리 안 상대 경로)를 옮겨 둘 휴지통 자리 `<워크트리 이름>~~<flatten(entry)>`.
    같은 자리가 있으면 `~<번호>` 를 붙인다."""
    base = root / TRASH_DIR / f"{name}~~{flatten(entry)}"
    slot = base
    counter = 1
    while os.path.lexists(slot):
        slot = base.with_name(f"{base.name}~{counter}")
        counter += 1
    return slot


def _move_aside(
    root: Path, path: Path, entries: Sequence[str], rename: Callable[[str, str], None]
) -> tuple[list[Path], bool]:
    """옮기기. 무시된 항목을 휴지통으로 이름 바꾸기 한다. 막히면 그 자리에서 멈추고 (옮긴 것,
    False) 를 돌려준다(막힌 항목과 그 뒤는 워크트리에 남는다). 올린 모듈은 이름 바꾸기를 막지
    않아(`lock_holder.py` 의 G, `worktree_occupancy.py` 의 E) 제자리 지우기가 막히던 자리
    (`module_holder.py` 의 G·E)를 지난다."""
    if not _ensure_trash(root):
        print(f"남겼다 {path.as_posix()} — {TRASH_REFUSED}")
        return [], False
    moved: list[Path] = []
    for entry in entries:
        source = path / entry.rstrip("/")
        # MAX_PATH 를 넘는 링크는 `\\?\` 없이 물으면 없는 것으로 보여, 옮기지 않은 링크를
        # `git worktree remove` 가 따라갔다(모듈 독스트링 판정 2)
        if not os.path.lexists(long_path(source)):
            continue
        slot = trash_slot(root, path.name, entry)
        try:
            rename(long_path(source), long_path(slot))
        except OSError as error:
            print(
                f"남겼다 {path.as_posix()} — 다시 만들 수 있는 {entry} 를 휴지통으로 옮기다 "
                f"막혔다({error}). 등록과 .git 은 남았다. 먼저 옮긴 것은 휴지통에서 지운다"
            )
            return moved, False
        moved.append(slot)
    return moved, True


def origin_of(root: Path, slot: Path) -> str:
    """휴지통 항목이 옮겨지기 전에 있던 자리(어림). 자리 이름은 `trash_slot` 의 것이다. 워크트리가
    `WORKTREES_DIR` 아래였다고 보고, 이름에 `~~` 가 든 워크트리와 `~<숫자>` 로 끝나는 경로는
    어긋난다 (못 보는 것). 올린 모듈의 매핑 이름은 옮기기 전 이름으로 남아(윈도의
    `GetMappedFileNameW`. 옮긴 뒤의 시험이 쥔 pid 를 대지 못했다, 일지 2026-10-15-06) 쥔 프로세스를
    그 이름으로도 찾는다."""
    name, _, flat = slot.name.partition("~~")
    flat = re.sub(r"~\d+$", "", flat)
    return (root / WORKTREES_DIR / name / unflatten(flat)).as_posix()


def _empty(entries: Sequence[Path], ops: Ops, root: Path) -> list[Path]:
    """휴지통 항목을 지운다. 막힌 것은 쥔 프로세스를 들어 찍고 남긴다. 프로세스는 처음 막혔을 때
    한 번 훑는다. 쥔 프로세스는 지금 자리와 옮기기 전 자리(`origin_of`) 둘로 찾는다."""
    left: list[Path] = []
    scanned: tuple[list[ProcessPath] | None, list[ProcessPath] | None] | None = None
    for entry in entries:
        try:
            ops.delete(entry)
        except OSError as error:
            if scanned is None:
                scanned = (ops.processes(), ops.modules())
            holders = combine_holders(
                holders_from(scanned[0], scanned[1], str(entry)),
                holders_from(scanned[0], scanned[1], origin_of(root, entry)),
            )
            print(
                f"휴지통에 남았다 {entry.as_posix()} — 지우다 막혔다({error}). "
                f"{describe_holders(holders)}. 다음 judge 가 다시 본다"
            )
            left.append(entry)
    return left


def _remove(
    root: Path, listing: list[Worktree], target: str, branch: str, head: str, ops: Ops
) -> int:
    """판정 4. 단계의 순서와 종료 코드는 모듈 독스트링."""
    wt = next((w for w in listing[1:] if same_path(w.path, target)), None)
    if wt is None:
        print(f"남겼다 {target} — 등록된 워크트리가 아니다")
        return 1
    wanted = None if branch == DETACHED else branch
    if (wt.branch, wt.head) != (wanted, head):
        print(f"남겼다 {target} — judge 뒤에 바뀌었다: 지금 {wt.branch} {wt.head}")
        return 1
    merged = ops.merged(root)
    first = _still_candidate(root, wt, merged, ops, "지우기 전에", ())
    if first is None:
        return 1
    if not first[1].exists:
        return _drop_registration(root, wt, ops.git)
    if _dead(wt, first[1]):
        return _remove_dead(root, wt, ops)
    stop = _probe(Path(wt.path), ops)
    if stop is not None:
        return stop
    # 판정 뒤에 생긴 것(`.env`, 새 파일, 작업 디렉터리 주인)을 옮기지 않게, 쥔 프로세스까지 다시
    # 판정해 옮길 목록을 읽는다. 리눅스의 탐침은 작업 디렉터리를 보지 못한다(PR #184 리뷰)
    holders = holders_in(ops.processes(), wt.path)
    again = _still_candidate(root, wt, merged, ops, "옮기기 직전에", holders)
    if again is None:
        return 1
    verdict, facts = again
    if verdict.unlock and not _unlock(root, wt, ops.git):
        return 1
    moved, done = _move_aside(root, Path(wt.path), facts.ignored, ops.rename)
    if not done:
        _empty(moved, ops, root)
        return 1
    code = _git_remove(root, wt.path, wanted, ops.git)
    _empty(moved, ops, root)
    return code


def _dead(wt: Worktree, facts: Facts) -> bool:
    """등록은 prunable 인데 `.git` 없는 폴더가 남은 것(지우다 만 폴더)."""
    return wt.prunable and facts.exists and not facts.has_git


def _remove_dead(root: Path, wt: Worktree, ops: Ops) -> int:
    """지우다 만 폴더를 등록 없는 폴더처럼 판정해 휴지통으로 옮기고 등록을 걷는다. git 은 폴더가
    있는 채로는 prunable 등록을 걷지 않는다(`validation failed`, 임시 저장소에서 손으로 봤다)."""
    path = Path(wt.path)
    reachable = _reachable(root, ops.git)
    if _still_stray(root, path, reachable, "등록을 걷기 전에", ()) is None:
        return 1
    moved = _move_whole(root, path, reachable, ops)
    if isinstance(moved, int):
        return moved
    code = _drop_registration(root, wt, ops.git)
    _empty([moved], ops, root)
    return code


def _move_whole(
    root: Path, path: Path, reachable: Callable[[], frozenset[str]], ops: Ops
) -> Path | int:
    """등록 없는 폴더(또는 지우다 만 폴더)를 탐침과 재판정을 거쳐 폴더째 휴지통으로 옮긴다. 옮긴
    자리를 돌려주고, 멈추면 종료 코드를 돌려준다."""
    stop = _probe(path, ops)
    if stop is not None:
        return stop
    if _still_stray(root, path, reachable, "옮기기 직전에", holders_now(ops, str(path))) is None:
        return 1
    if not _ensure_trash(root):
        print(f"남겼다 {path.as_posix()} — {TRASH_REFUSED}")
        return 1
    slot = trash_slot(root, path.name, "")
    try:
        ops.rename(long_path(path), long_path(slot))
    except OSError as error:
        print(f"남겼다 {path.as_posix()} — 휴지통으로 옮기다 막혔다({error})")
        return 1
    return slot


def _drop_registration(root: Path, wt: Worktree, git: GitRunner) -> int:
    """폴더가 없는 등록을 걷는다. git 2.32 의 `worktree remove` 는 폴더가 없으면 등록만 걷는다
    (임시 저장소에서 손으로 봤다, 일지 2026-10-15-06). 브랜치는 다음 `judge` 가 본다."""
    removed = git(["worktree", "remove", wt.path], root)
    if removed.returncode != 0:
        print(f"남겼다 {wt.path} — git worktree remove: {removed.stderr.strip()}")
        return 1
    print(f"걷었다 {wt.path} 의 등록. 브랜치 {wt.branch or '(분리 HEAD)'} 는 다음 judge 가 본다")
    return 0


def _still_candidate(
    root: Path,
    wt: Worktree,
    merged: Mapping[str, frozenset[str]],
    ops: Ops,
    moment: str,
    holders: Sequence[Holder] | None,
) -> tuple[Verdict, Facts] | None:
    """판정 1~3(세션은 빼고)을 다시 낸다. 지울 것이 아니면 이유를 찍고 None."""
    facts = gather(root, wt, ops.git, merged)
    verdict = judge(wt, facts, merged, (), ops.pid_alive, holders)
    if verdict.action != "delete":
        print(f"남겼다 {wt.path} — {moment} 다시 판정했다: {verdict.reason}")
        return None
    return verdict, facts


def _probe(path: Path, ops: Ops) -> int | None:
    """점유 탐침. 지나면 None, 막히면 1(바꾼 것 없음), 끝내 되돌리지 못하면 3.

    막혔을 때만 쥔 프로세스를 찾아 이유에 붙인다. 지나간 지우기는 옮기기 직전의 다시 거르기에서
    한 번 훑는다(판정 4의 2). 되돌리기는 `RESTORE_WAITS` 만큼 기다리며 다시 시도한다(대기열 202).
    """
    aside = path.with_name(path.name + PROBE_SUFFIX)
    if os.path.lexists(aside):
        print(f"남겼다 {path.as_posix()} — 탐침 자리 {aside.as_posix()} 가 이미 있다")
        return 1
    try:
        ops.rename(long_path(path), long_path(aside))
    except OSError as error:
        print(
            f"남겼다 {path.as_posix()} — 다른 프로세스가 쥐고 있다(이름 바꾸기가 막혔다: {error}). "
            f"{describe_holders(holders_now(ops, str(path)))}"
        )
        return 1
    failures: list[OSError] = []
    for wait in (0.0, *RESTORE_WAITS):
        if wait:
            ops.sleep(wait)
        try:
            ops.rename(long_path(aside), long_path(path))
        except OSError as error:
            failures.append(error)
            continue
        if failures:
            print(
                f"다시 시도해 되돌렸다 {path.as_posix()} — {len(failures) + 1}번째에 지났다. "
                f"처음 막힌 이유: {failures[0]}"
            )
        return None
    print(
        f"멈췄다 {path.as_posix()} — 폴더가 {aside.as_posix()} 에 남았다. 되돌리기를 "
        f"{len(failures)}번 시도했다: {failures[-1]}"
    )
    return 3


def _unlock(root: Path, wt: Worktree, git: GitRunner) -> bool:
    unlocked = git(["worktree", "unlock", wt.path], root)
    if unlocked.returncode != 0:
        print(f"남겼다 {wt.path} — 잠금을 풀지 못했다: {unlocked.stderr.strip()}")
        return False
    return True


def _git_remove(root: Path, path: str, branch: str | None, git: GitRunner) -> int:
    removed = git(["worktree", "remove", path], root)
    if removed.returncode != 0:
        print(
            f"멈췄다 {path} — git worktree remove 가 {removed.returncode} 로 끝났다: "
            f"{removed.stderr.strip()}. 등록과 .git 파일이 지워졌을 수 있다"
        )
        return 3
    if branch is None:
        print(f"지웠다 {path} (분리 HEAD)")
        return 0
    deleted = git(["branch", "-D", branch], root)
    if deleted.returncode != 0:
        print(f"지웠다 {path}, 브랜치는 남았다 — git branch -D: {deleted.stderr.strip()}")
        return 1
    print(f"지웠다 {path} 와 브랜치 {branch}")
    return 0


def _remove_branch(root: Path, listing: list[Worktree], branch: str, tip: str, ops: Ops) -> int:
    if any(same_branch(wt.branch, branch) for wt in listing):
        print(f"남겼다 {branch} — 체크아웃돼 있다")
        return 1
    current = ops.git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root)
    if current.returncode != 0 or current.stdout.strip() != tip:
        print(f"남겼다 {branch} — judge 뒤에 바뀌었다: 지금 {current.stdout.strip() or '없음'}")
        return 1
    # `remove` 처럼 다시 판정할 때는 세션을 보지 않는다(모듈 독스트링)
    merged = ops.merged(root)
    contained = contains(root, tip, ops.git)
    behind = behind_merged(root, tip, merged.get(branch), ops.git)
    fresh = _fresh(root, branch, merged, ops.git, ops.now(), contained=contained)
    verdict = judge_branch(branch, tip, merged, (), contained=contained, behind=behind, fresh=fresh)
    if verdict.action != "delete":
        print(f"남겼다 {branch} — 다시 판정했다: {verdict.reason}")
        return 1
    deleted = ops.git(["branch", "-D", branch], root)
    if deleted.returncode != 0:
        print(f"남겼다 {branch} — git branch -D: {deleted.stderr.strip()}")
        return 1
    print(f"지웠다 브랜치 {branch}")
    return 0


def _remove_stray(root: Path, listing: list[Worktree], target: str, ops: Ops) -> int:
    """등록 없는 폴더 하나를 지운다. 단계의 순서와 종료 코드는 모듈 독스트링의 "등록 없는 폴더"."""
    # 인자를 그대로 쓰지 않고 목록에서 찾은 폴더를 쓴다. 이후 단계가 같은 자리를 본다
    path = next((stray for stray in _strays(root, listing) if same_path(target, str(stray))), None)
    if path is None:
        print(f"남겼다 {target} — {WORKTREES_DIR}/ 바로 아래의 등록 없는 폴더가 아니다")
        return 1
    reachable = _reachable(root, ops.git)
    if _still_stray(root, path, reachable, "지우기 전에", ()) is None:
        return 1
    moved = _move_whole(root, path, reachable, ops)
    if isinstance(moved, int):
        return moved
    left = _empty([moved], ops, root)
    print(f"지웠다 {path.as_posix()}" + (" (휴지통에 일부가 남았다)" if left else ""))
    return 0


def _end_holders(
    root: Path,
    listing: list[Worktree],
    target: str,
    sessions: Sequence[str],
    own: str | None,
    ops: Ops,
) -> int:
    """워크트리를 작업 디렉터리로 쥔 프로세스를, 모두 `sessions` 의 것일 때만 끝낸다. 순서와 종료
    코드는 모듈 독스트링의 "쉬는 세션의 프로세스"."""
    wrong = [session for session in sessions if not _SESSION_ID.fullmatch(session)]
    if wrong:
        print(f"세션 id 모양(local_<uuid>)이 아니다: {', '.join(wrong)}", file=sys.stderr)
        return 2
    if own is None or not _SESSION_ID.fullmatch(own):
        print(f"남겼다 {target} — 부른 세션을 모른다(환경의 {SESSION_ENV} 가 없거나 어긋난다)")
        return 1
    if own in sessions:
        print(f"남겼다 {target} — 이 도구를 부른 세션({own})은 끝내지 않는다")
        return 1
    wt = next((w for w in listing[1:] if same_path(w.path, target)), None)
    if wt is None:
        print(f"남겼다 {target} — 등록된 워크트리가 아니다")
        return 1
    found = with_lock(holders_in(ops.processes(), wt.path), wt, ops.pid_alive)
    if found is None:
        print(f"남겼다 {wt.path} — 이 OS 에서 프로세스를 볼 수 없거나 읽다 실패했다")
        return 1
    if not found:
        print(f"끝낼 것이 없다 {wt.path} — 쥔 프로세스가 없다. judge 를 다시 친다")
        return 0
    owners = sessions_of(found, ops.session_of)
    strangers = [holder for holder in found if owners.get(holder.pid) not in sessions]
    if strangers:
        described = describe_holders(strangers, owners)
        print(f"남겼다 {wt.path} — 받은 세션 밖의 프로세스가 쥐었다. 끝낸 것은 없다: {described}")
        return 1
    # `remove` 처럼 끄기 전에 판정 1~3을 다시 낸다. `judge` 뒤에 고친 파일이나, 찍힌 적 없는 줄을
    # 친 병합되지 않은 워크트리의 프로세스를 끄지 않는다. 실행 중 세션은 부르는 쪽이 이 명령을
    # 치기 직전에 `list_sessions` 로 다시 본다(스킬 3.2)
    merged = ops.merged(root)
    facts = gather(root, wt, ops.git, merged)
    again = judge(wt, facts, merged, (), ops.pid_alive, found, owners=owners, idle=sessions)
    if again.action != "end":
        print(f"남겼다 {wt.path} — 끄기 전에 다시 판정했다: {again.reason}. 끝낸 것은 없다")
        return 1
    for holder in found:
        name = f"{holder.image or '(이름 모름)'}(pid {holder.pid})"
        # 끄기 직전에 세션 id 를 다시 읽는다. 훑은 뒤 그 pid 가 끝나 다른 프로세스가 받았으면 값이
        # 다르다. pid 만 보고 끄지 않는다(`.claude/rules/probes.md`). 앞 프로세스를 끄며 함께
        # 끝났으면 읽지 못한다(None)
        now = ops.session_of(holder.pid)
        if now is None:
            continue
        if now != owners[holder.pid]:
            print(f"건너뛰었다 {name} — 훑은 뒤 세션 id 가 {now} 로 바뀌었다")
            continue
        if not ops.end(holder.pid):
            print(f"끄지 못했다 {name}")
    # 끄기를 부른 뒤에도 프로세스가 끝나기까지 틈이 있어 기다리며 다시 훑는다
    left = with_lock(holders_in(ops.processes(), wt.path), wt, ops.pid_alive)
    for wait in END_WAITS:
        if left is not None and not left:
            break
        ops.sleep(wait)
        left = with_lock(holders_in(ops.processes(), wt.path), wt, ops.pid_alive)
    if left is not None and not left:
        ended = describe_holders(found, owners)
        print(
            f"끝냈다 {wt.path} 를 쥔 프로세스 — {ended}. 세션은 사이드바에 남고 다시 띄우면 "
            "대화가 이어진다. judge 를 다시 친다"
        )
        return 0
    print(f"남겼다 {wt.path} — 아직 쥔 프로세스가 있다: {describe_holders(left)}")
    return 1


def _restore(root: Path, listing: list[Worktree], target: str, ops: Ops) -> int:
    """점유 탐침이 옆 이름에 남긴 폴더를 원래 이름으로 되돌린다. 원래 이름의 등록이 폴더를 잃은
    채 남아 있을 때만이다."""
    aside = Path(target)
    if not aside.name.endswith(PROBE_SUFFIX) or not aside.is_dir():
        print(f"남겼다 {target} — {PROBE_SUFFIX} 로 끝나는 폴더가 아니다")
        return 1
    home = aside.with_name(aside.name.removesuffix(PROBE_SUFFIX))
    if not any(same_path(str(home), wt.path) for wt in listing[1:]):
        print(f"남겼다 {target} — {home.as_posix()} 의 등록이 없다")
        return 1
    if os.path.lexists(home):
        print(f"남겼다 {target} — {home.as_posix()} 가 이미 있다")
        return 1
    try:
        ops.rename(long_path(aside), long_path(home))
    except OSError as error:
        print(f"남겼다 {target} — 되돌리다 막혔다({error})")
        return 1
    print(f"되돌렸다 {home.as_posix()}. 다음 judge 가 다시 본다")
    return 0


def _ensure_trash(root: Path) -> bool:
    """휴지통 폴더를 만든다. 그 자리가 링크거나 폴더가 아니면 만들지 않고 False."""
    if trash_dir(root) is None:
        return False
    (root / TRASH_DIR).mkdir(parents=True, exist_ok=True)
    return True


def _empty_trash(root: Path, ops: Ops) -> int:
    if trash_dir(root) is None:
        print(_trash_refused(root))
        return 1
    entries = _trash_entries(root)
    if not entries:
        print("휴지통이 비어 있다")
        return 0
    left = _empty(entries, ops, root)
    for entry in entries:
        if entry not in left:
            print(f"지웠다 {entry.as_posix()}")
    return 1 if left else 0


def _still_stray(
    root: Path,
    path: Path,
    reachable: Callable[[], frozenset[str]],
    moment: str,
    holders: Sequence[Holder] | None,
) -> Verdict | None:
    """등록 없는 폴더의 판정을 다시 낸다. 지울 것이 아니면 이유를 찍고 None."""
    facts = gather_stray(root, path, reachable)
    verdict = judge_stray(path.as_posix(), facts, holders)
    if verdict.action != "delete":
        print(f"남겼다 {path.as_posix()} — {moment} 다시 판정했다: {verdict.reason}")
        return None
    return verdict


def _parser() -> argparse.ArgumentParser:
    # 스킬 3은 독스트링을 파일 전체 Read 대신 `--help` 로 본다(대기열 271)
    parser = argparse.ArgumentParser(
        prog="tidy_checkouts",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    judged = commands.add_parser("judge", help="워크트리와 로컬 브랜치를 판정해 찍는다")
    judged.add_argument(
        "--running",
        action="append",
        default=[],
        help="실행 중 세션의 제목이나 브랜치(list_sessions 의 title, branch)",
    )
    judged.add_argument(
        "--idle",
        action="append",
        default=[],
        help="프로세스를 끝내도 되는 쉬는 세션의 id(list_sessions 의 sessionId)",
    )
    ended = commands.add_parser("end-holders", help="워크트리를 쥔 쉬는 세션의 프로세스를 끝낸다")
    ended.add_argument("path")
    ended.add_argument("sessions", nargs="+")
    removed = commands.add_parser("remove", help="워크트리 후보 하나를 지운다")
    removed.add_argument("path")
    removed.add_argument("branch")
    removed.add_argument("head")
    branch = commands.add_parser("remove-branch", help="체크아웃되지 않은 브랜치 하나를 지운다")
    branch.add_argument("branch")
    branch.add_argument("tip")
    stray = commands.add_parser("remove-stray", help="등록 없는 워크트리 폴더 하나를 지운다")
    stray.add_argument("path")
    restore = commands.add_parser("restore", help="탐침이 옆 이름에 남긴 폴더를 되돌린다")
    restore.add_argument("path")
    commands.add_parser("empty-trash", help="휴지통에 남은 것을 지운다")
    return parser


def main(
    argv: Sequence[str] | None = None, *, cwd: Path | None = None, ops: Ops | None = None
) -> int:
    args = _parser().parse_args(argv)
    tools = ops if ops is not None else Ops()
    try:
        root, listing = _place(cwd if cwd is not None else Path.cwd(), tools.git)
    except ValueError as error:
        print(f"주 체크아웃 세션에서 돈다: {error}", file=sys.stderr)
        return 2
    except ToolError as error:
        print(error, file=sys.stderr)
        return 3
    try:
        return _dispatch(args, root, listing, tools)
    except ToolError as error:
        print(error, file=sys.stderr)
        return 3


def _dispatch(args: argparse.Namespace, root: Path, listing: list[Worktree], tools: Ops) -> int:
    """하위 명령 하나를 돌리고 그 종료 코드를 돌려준다."""
    command: str = args.command
    # 이 도구를 부른 세션. 앱이 넣은 환경을 셸과 uv 를 거쳐 물려받는다
    own = os.environ.get(SESSION_ENV)
    if command == "judge":
        running: list[str] = args.running
        requested: list[str] = args.idle
        idle = frozenset(session for session in requested if session != own)
        return _judge_all(root, listing, running, idle, tools)
    if command == "end-holders":
        sessions: list[str] = args.sessions
        return _end_holders(root, listing, args.path, sessions, own, tools)
    if command == "remove":
        return _remove(root, listing, args.path, args.branch, args.head, tools)
    if command == "remove-stray":
        return _remove_stray(root, listing, args.path, tools)
    if command == "restore":
        return _restore(root, listing, args.path, tools)
    if command == "empty-trash":
        return _empty_trash(root, tools)
    return _remove_branch(root, listing, args.branch, args.tip, tools)


if __name__ == "__main__":
    sys.exit(main())
