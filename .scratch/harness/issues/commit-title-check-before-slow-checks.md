# commit-title-check-before-slow-checks: 커밋 제목의 타입과 72자 제한을 8분 걸리는 검사 러너보다 먼저 보게 한다

**What to build:** `tools/hook_bash_commit_msg.py`가 보는 커밋 명령의 꼴을 넓힌다. 지금은 `git commit -F <파일>`만 판정해서, 제목이 72자를 넘거나 타입이 틀려도 `-m`으로 친 커밋, `cd <폴더> && git commit …`처럼 앞에 폴더 이동이 붙은 복합 명령, 메시지를 표준 입력으로 넘기는 `git commit -F - <<'EOF'`는 훅이 그냥 지나간다. 그러면 pre-commit의 `parallel-checks`가 6~20분을 돈 뒤에야 `commit-msg` 단계가 같은 제목을 막는다. 아홉 번 그랬다(대기열 항목의 회차 서술이 원천이다).

넓히는 꼴은 넷이다.

- `-m <메시지>`와 `--message`. `-m`이 여럿이면 git처럼 빈 줄 하나로 이은 글을 본다.
- `cd <폴더>`나 `pushd <폴더>` 뒤에 `&&`나 `;`로 이어진 커밋. 상대 경로는 이동한 폴더에서 푼다. 이동한 곳을 알 수 없으면(`cd -`, 변수가 든 경로, 파이프와 `||` 뒤의 이동, 괄호 안) 지금처럼 보지 않는다.
- `-F -`와 메시지를 담은 heredoc. 구분자에 따옴표를 붙인 heredoc은 본문을 글자 그대로 본다. 따옴표가 없는 heredoc은 본문에 `$`·백틱·역슬래시가 없을 때만 본다(있으면 셸이 풀어 본문이 달라진다).
- `-m "$(cat <<'EOF' … EOF)"`. 에이전트가 커밋할 때 가장 흔한 꼴이다. 같은 줄에서 연 heredoc의 본문을 메시지로 본다.

판정은 옮겨 적지 않는다. 메시지를 임시 파일에 쓰고 `tools/check_commit_msg.py`를 자식 프로세스로 그대로 부른다. 막는 대상은 지금과 같은 "실수로 내는 길"이고 우회(`--no-verify`, `SKIP`, `-e` 등)는 지금처럼 보지 않는다. `-m`은 `-F`·`-C`·`-c`와 함께 쓰면 git이 오류로 끝내므로 그 조합도 보지 않는다.

훅을 넓히므로 `.claude/rules/tools.md`의 규약대로 넓힌 꼴마다 실제 명령 모양으로 발동하는지 손으로 확인하고(`tools/hook_payloads.toml`의 발동·무발동 입력과 `tools/run_hooks.py` 실행), 새 갈래마다 시험 하나로 고정하고, 변이 표(`tools/mutate.py`)로 시험이 빨개지는지 본다. 독스트링의 "못 보는 것"을 새 범위에 맞게 고친다.

**대기열:** commit-msg-after-slow-checks

**Status:** done

- [x] `-m`(여럿, `--message=`, `-am`), `cd`·`pushd` 뒤의 커밋, `-F -` heredoc, `-m "$(cat <<'EOF' …)"`의 제목이 72자를 넘거나 타입이 틀리면 훅이 막고, 제목이 맞으면 지나간다(`tests/tools/test_hook_bash_commit_msg.py`)
- [x] 보지 않는 길(`--no-verify`와 그 줄임(`--no-verif`, `--dry` 등), `--config-env=core.hooksPath=…`, `SKIP=…commit-msg…`, `-e`, `-F`나 `-C`와 섞인 `-m`, 따옴표 없는 heredoc 본문의 `$`, 이동한 곳을 모르는 `cd`(`cd -`, `cd ~user`, `pushd +1`, `then cd`, 중괄호), `-F - < 파일`, `echo … |`로 넘긴 메시지)은 지나간다는 시험이 있다
- [x] 실제 `git commit` 명령 꼴(`-m`, `cd … &&` 복합, `-F -`)이 `tools/hook_payloads.toml` 사례로 발동과 무발동을 하나씩 갖고 `uv run python tools/run_hooks.py`가 초록이다
- [x] `.scratch/harness/probes/` 아래 변이 표가 새 갈래마다 빨강을 잡고, `uv run python tools/mutate.py <표>`가 기대대로 돈다
- [x] 독스트링(`tools/hook_bash_commit_msg.py`)의 막는 대상, 찾는 것, 못 보는 것이 새 범위와 맞고 `.claude/rules/tools.md`의 이 훅 시간 줄이 새 길을 반영한다
- [x] 대기열 항목 `commit-msg-after-slow-checks`의 상태 줄이 이 티켓으로 닫혀 있다(대기열 README의 "닫을 때는 상태 줄 하나만 고친다"). 훅이 못 보는 길은 독스트링에 남는다
- [x] 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)과 지침 검사(`tools/check_instructions.py`)가 초록이다

## Comments
