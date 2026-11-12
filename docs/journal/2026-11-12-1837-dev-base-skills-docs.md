# dev-base-skills-docs: 스킬과 규약 문서를 기준 브랜치 규칙에 맞춘다 · 2026-11-12

`next-session`이 낸 지시문(나란히 여는 3 중 3)을 사용자가 붙여 넣어 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/dev-branch/issues/03-dev-base-skills-docs.md`이고, 브랜치는 `feature/03-dev-base-skills-docs`, 작업은 `EnterWorktree`로 들어간 워크트리 `03-dev-base-skills-docs`에서 했다. 이번 요청 범위는 "PR과 병합까지"다. 준비, 한 것, 셀프 리뷰, 회고, 검증, 다음을 차례로 둔다.

## 준비

- 주 체크아웃(루트는 main)에서 시작해 `EnterWorktree`로 들어갔고, 세션 제목을 브랜치 이름으로 바꿨다. `tidy-checkouts`는 묶음의 첫 세션이 돈다는 지시문대로 이 세션에서는 돌지 않았다.
- 읽은 것: 일지 `2026-11-12-1419-dev-branch-model`의 "다음", 나란히 도는 티켓 01·02(02는 형제 워크트리의 사본), agent-os 티켓 `dev-base-skills-docs`와 그 PR(#537, #541)의 diff. agent-os는 읽기만 했다.

## 한 것

- 스킬: `next-session`(`SKILL.md`, `directive.md`, `merge.md`), `tidy-checkouts`, `code-review`, `open-session`, `retro`, `implement`, 에이전트 둘(`bug-perf-review`, `spec-reviewer`), 규칙 `adr.md`, PR 템플릿. 곳마다 `main`의 뜻(기준 브랜치, 운영 브랜치, 루트 브랜치)을 가른 표는 티켓 끝 "결과 1"에 있다.
- `merge.md`: "병합 방법"(PR 종류별 base와 병합 방식 표, 보호 설정, 늦게 병합할 때 기준 브랜치를 합치고 `test_plan_status`를 직접 돌리는 순서)과 "되돌려 합치기"(PR로만 한다. 필요 판정은 `git merge-base --is-ancestor origin/main origin/dev`)를 적었다. 결정표의 첫 줄이 되돌려 합칠 것이 남았는지 본다. "hotfix가 사라진다"는 옮기지 않았고 출시 PR을 여는 순서는 05에 맡겼다.
- 문서: `CLAUDE.md`, `docs/constitution/operations.md`("브랜치와 병합"의 용어 여덟과 기준 브랜치 규칙, "가드레일"의 보호 브랜치 둘, "리뷰 파이프라인"의 `/security-review`·리뷰 봇·CodeRabbit), 헌법 판 1.1.2 → 1.2.0, `docs/agents/issue-tracker.md`, `tests/test_plan_status.py` 머리 독스트링, ADR 0016(본문은 두고 포인터와 `## 이력`).
- CodeRabbit 확인: 공식 문서 원문(`auto-review.md`)을 `curl`로 내려받아 읽었다. 수동 호출이 base와 무관하게 되는지는 문서가 따로 말하지 않아 어림으로 적고 첫 핫픽스 PR에서 볼 일로 남겼다(티켓 끝 "결과 3").

## 셀프 리뷰

`code-review` 두 축. base `e95006cc`, 바뀐 추적 파일 열아홉(미추적 일지 하나는 리뷰 뒤에 썼다), 커밋 0. 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다.

- 하드 위반 셋(표준 축).
  - merge.md "병합 방법"의 사용자 승인을 어느 줄에서도 받지 않는다는 문장이 병합 길 4(ADR·헌법을 담은 PR은 병합 전에 승인)와 어긋났다. → 고쳤다. 병합 방법을 묻지 않는다는 뜻으로 좁히고 승인이 필요한 PR은 4가 정한다고 적었다.
  - ADR 0016 본문 문장을 고쳐 썼다(`.claude/rules/adr.md`의 "본문의 다른 글자는 고치지 않는다"). → 고쳤다. 본문을 원래 문장으로 되돌리고 끝 문장 뒤에 포인터만 달았으며 결과는 `## 이력`에 적었다. `tools/check_adr_pointers.py`가 통과한다.
  - 02의 결정(알려진 빨강, 되돌려 합치기 PR은 돈다)이 이 트리에 없다. → 남겼다. 02가 병합되기 전에는 근거가 이 트리에 없으므로 이 PR은 02가 병합된 뒤에 병합한다(티켓 03의 첫 수락 기준). 이력에는 그 결정이 02 티켓에서 옮긴 것이고 액션 소스를 이 저장소에서 다시 읽지 않았다고 적었다.
- `tools/wait_ci.py`의 `judge()`가 `--expect`와 무관하게 CodeRabbit의 "Review skipped"를 요청되지 않은 리뷰로 세어 종료 4로 끝난다(코드를 읽었다: `UNREQUESTED_PREFIX`, `unrequested`). → 고쳤다. 되돌려 합치기 3단계에 종료 0 또는 4는 예상한 끝이고 1이나 3이면 병합하지 않는다고 적었다.
- 갈래 밟기.
  - 되돌려 합치기의 필요 판정이 `git diff`(내용)라 출시 PR의 merge 커밋이 dev에 없어도 "합칠 것 없음"이 됐다. main의 strict 때문에 다음 출시 PR이 뒤처졌다고 막힌다. → 고쳤다. `merge-base --is-ancestor`로 바꿨다(agent-os 체크아웃의 `merge.md`·`SKILL.md`가 같은 판정을 쓰는 것을 읽었다). 출시 PR을 병합한 세션도 되돌려 합친다고 적었다.
  - operations.md의 `/git-pr-merge` 문장이 출시 PR의 base도 main이라 자기모순이었다. → 고쳤다.
  - 표의 티켓 PR 줄이 주 체크아웃의 병합 길과 어긋났다. → 고쳤다. `docs/*` 면제 PR이 티켓 PR 정의와 충돌하던 것도 표의 라벨로 나눴다.
  - 칩 문장(기본 브랜치가 어디인지), issue-tracker 첫 항목의 모호한 문장, operations.md "PR:" 줄을 고쳤다.
  - 열린 되돌려 합치기 PR만 남은 재진입은 결정표가 고르지 않고, 되돌려 합치기 1이 그 PR을 찾아 3부터 잇는다고 적었다. 별도 재진입 절은 두지 않았다.
- 남긴 것: 헌법 판을 minor로 올린 것은 판단이다(절 추가가 아니라 기존 세 절에 규칙 항목을 더했다. 규칙과 정의의 추가라 minor로 두었다). 기준 브랜치 규칙이 여러 문서에 되풀이되는 것(Duplicated Code 냄새)은 각 문서가 읽는 때가 달라 두었다. 도구 쪽(`tools/base_rule.py` 등)은 01이 병합되기 전이라 문서가 앞서간다. 01이 병합된 뒤에 병합한다.
- 다시 돌린 명령: `uv run ruff check .`와 `uv run ruff format --check .` 초록, `uv run python tools/sibling_overlap.py` 0, `uv run python tools/check_adr_pointers.py` 0, 새 헤드리스 세션(`claude -p`)에서 `next-session` 스킬을 불러 결정표 첫 줄의 판정 명령이 바뀐 것으로 나옴을 확인했다.

## PR 직전 리뷰

`coderabbit-review`가 CodeRabbit CLI(`coderabbit review --agent --include-untracked --base origin/main`)를 돌리려 했으나 자동 모드 분류기가 외부 서비스로 diff를 보내는 명령이라며 거절했다. 우회하지 않았고 다시 시도하지 않았다. 운영 문서 "리뷰 파이프라인"의 대체 둘을 돌렸다.

- `/security-review`(내장). 코드 변경은 `tests/test_plan_status.py`의 독스트링뿐이고 나머지는 마크다운 문서라 보고할 취약점이 없었다.
- `bug-perf-review`(기준 `e95006cc`, 21파일). 밀 주장 6건(되돌려 합치기의 `is-ancestor` 판정, `wait_ci.py`의 종료 4, `delete_branch_on_merge`가 false, 기준 브랜치 합치기 뒤 `test_plan_status` 직접 실행, `/git-pr-merge`의 가정, 결정표 첫 줄)은 코드와 실측에 맞았다고 했다. 지적 여섯(Major 1, Minor 5)은 모두 유효했다.
  - Major. 끊긴 되돌려 합치기 PR을 이어받는 세션이 없다(결정표 첫 줄이 열린 PR을 일률로 사용자에게 넘긴 것으로 거른다). → 고쳤다. `CONFLICTING`·`BEHIND`가 아니고 넘긴다는 기록이 없는 열린 PR은 끊긴 것으로 보고 첫 줄이 고른다. 되돌려 합치기 1이 그 PR을 찾아 3부터 잇는다.
  - Minor. `--match-head-commit`을 "언제나" 붙인다는 문장이 `/git-pr-merge` 길과 모순된다. → 고쳤다. 이 파일이 직접 치는 병합 명령에 한정하고 `/git-pr-merge` 길은 병합 길 4의 `headRefOid` 대조가 맡는다고 적었다.
  - Minor. 되돌려 합치기 3이 `--head`를 `git rev-parse origin/main`으로 읽고 verify 줄 없는 종료 4와 2의 처리가 없다. → 고쳤다. 띄우기 직전 `gh pr view <번호> --json headRefOid`로 읽고, verify 줄이 없는 4와 2는 3을 다시 띄운다.
  - Minor. 핫픽스가 `claude-code-review.yml`을 바꾸면 되돌려 합치기 PR에서 코멘트 0개 가드가 빨개질 수 있다. → 고쳤다. 실패가 `claude-review`뿐인 종료 1도 사용자에게 넘긴다고 적었다(필수 검사가 아니므로 병합할지는 사용자가 정한다).
  - Minor. dev를 합친 푸시 뒤 봇 대기를 처음부터 다시 하는 비용이 크다. → 남겼다. 봇 재요청을 빼는 것은 리뷰의 범위를 좁히는 일이라 사용자가 정할 일이고, 이 PR에서는 지금 규칙(푸시마다 봇 회차)을 두었다.
  - Minor. `tidy-checkouts`와 운영 문서가 01의 도구를 있는 것처럼 쓴다. → 남겼다. 티켓 03의 첫 수락 기준이 01 병합 뒤의 병합을 요구하고, PR 본문 맨 위에도 적는다.
  - 비고(Minor). 운영 문서가 main의 strict를 05가 정한다고 하면서 가드레일 절에서는 현재 사실로 쓴다. → 남겼다. 05가 strict를 풀면 되돌려 합치기 필요 판정의 근거 문장도 함께 고친다.
- 다시 돌린 명령: 반영 뒤 커밋의 pre-commit 결과는 PR 본문에 적는다.

## PR 봇 리뷰 (첫 회차)

PR #25를 연 뒤 `@coderabbitai review`를 남겼다. CI는 `python`, `image`, `ticket`, `verify`, `claude-review`가 통과했다. CodeRabbit은 무료 OSS 리뷰 한도에 걸려 리뷰를 내지 않았다(`Review rate limited`, 7분 뒤 다시 가능). 한도에 걸린 푸시는 회차로 세지 않는다(`next-session` `merge.md`의 회차 세기). claude-review의 첫 리뷰가 첫 회차라 Minor·Nit도 지적마다 판단했다.

- claude-review Minor 1(운영 문서 가드레일 절이 아직 없는 `tools/protection-dev.json`을 현재형으로 가리킨다): → 고쳤다. "티켓 `04-dev-branch-create`가 만드는" 생성 주체를 밝혔다.
- claude-review Minor 2(`tools/base_rule.py`가 이 트리에 없다): → 보류. 01 병합 뒤에 병합한다는 게이트가 PR 본문 맨 위, 티켓 03의 첫 수락 기준, 이 일지 "다음"에 있다.
- claude-review Nit 3(`agent-os` 이름이 헌법 본문에 든다): → 보류. 원칙 III과 ADR 0016이 하네스 원천으로서의 언급이라고 선을 그었고, 낱말 검사가 생기면 그때 대기열 `client-name-in-spec-body`가 걸 자리다.

반영으로 새로 쓴 사실 문장(원문): "dev(티켓 `04-dev-branch-create`가 만드는 `tools/protection-dev.json`)는 같되 strict가 아니다."

## 회고

후보 다섯. 승인 하나, 기각 셋, 일지에만 하나, 넘김 없음. 새 훅·검사가 문턱을 지난 것이 없어 `tools/hook_report.py`는 돌리지 않았다. `uv run python tools/queue_open_rows.py`의 만료할 항목은 없었다.

1. 승인(새 항목 `adr-body-rewrite-vs-pointer` 1회차). 사건: 티켓 03의 수락 기준이 ADR 0016의 추론 문장을 "고쳤고"라고 적었고, 세션이 본문 문장을 다시 쓰고 포인터를 달아 `.claude/rules/adr.md`의 "본문의 다른 글자는 고치지 않는다"를 어겼다(표준 축 하드 위반 2). 층: 지침(`adr.md`) 위의 검사(`tools/check_adr_pointers.py` 쪽에서 본문의 지운 줄이 포인터만 덧붙인 것인지 판정)로 승인했다. 되돌림: PR 하나. 더하는 것이라 다섯 번째에 반영하고 대기열에 둔다. 티켓 문구가 규칙과 어긋난 것도 한 원인이다. `rules-skipped-on-bash-read`와는 원인이 달라(그 항목은 규칙이 실리지 않은 것) 잇지 않았다.
2. 기각. 되돌려 합치기 3단계가 `tools/wait_ci.py`의 종료 4를 코드를 읽지 않고 적은 것을 명세 축이 짚었다. `code-review`의 두 브리프에 있는 주장 검증(9 부르는 쪽의 길, 10 코드의 동작)이 잡도록 둔 기준이고 리뷰가 제 몫을 했다.
3. 기각. 필요 판정을 `git diff`로 옮긴 것은 agent-os가 `is-ancestor`로 바꾼 뒤였다(표준 축의 갈래 밟기가 잡았다). 두 저장소의 벌어짐을 알리는 일은 agent-os의 대기열 `rag-engine-harness-drift` 몫이다.
4. 기각. 워크트리 가드가 `git -C`와 복잡한 명령, 40줄 넘는 heredoc을, Grep 훅이 `.env`에 닿는 glob을 막거나 알렸다. 있는 훅이 그 자리에서 막았다.
5. 일지에만. `claude -p --allowedTools Skill Read`는 첫 시도에서 가변 인자가 프롬프트를 삼켰고(프롬프트를 stdin으로 주어 해결), 한 번의 환경 함정이라 항목으로 잇지 않는다.

## 검증

- `uv run ruff check .`와 `uv run ruff format --check .`는 초록이었다(508개 파일).
- `uv run python tools/run_checks.py`(셀프 리뷰 반영 뒤 일지와 대기열 항목을 쓰기 전의 트리)는 test-db, zizmor, check-ticket, lint-imports, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks, pytest(671.9초)가 모두 Passed로 끝났다(종료 0).
- `uv run python tools/sibling_overlap.py`는 0이었고 "번호 겹침 없음", 헌법 판 1.2.0이었다. `uv run python tools/check_adr_pointers.py`는 0이었다. 열린 PR #24(02)의 헌법 판은 올리지 않아 판 겹침이 없다.
- 새 헤드리스 세션(`claude -p`)이 `next-session` 스킬을 불러 결정표의 첫 줄이 `git merge-base --is-ancestor origin/main origin/dev`임을 답했다. 바뀐 스킬이 새 세션에 실린다.
- 첫 커밋 시도의 pre-commit은 pytest 1개 실패, 3730개 통과(555.7초)로 막혔다. 실패는 앞 일지에도 난 `tests/adapters/test_parse_runner.py`의 멈춘 자식 시험(Windows 기대 `parse_failed`에 `parse_timeout`이 왔다)이고 이 브랜치는 파서 쪽 파일을 바꾸지 않았다. 단독으로 다시 돌리니 1 passed(1.76초)였다. 부하에서만 빨간 시간 시험은 받아들여 닫은 종류라 항목을 잇지 않는다(retro 5단계). 같은 시도의 인용 대조 경고 둘은 따옴표를 떼고 풀어 썼다.
- 둘째 시도의 pre-commit 결과는 PR 본문에 적는다.

## 다음

- 이 브랜치를 `origin/main` 위로 리베이스해 푸시하고 PR(base main, 지금은 dev가 없다)을 연다. 병합은 하지 않는다. 2026-11-12에 `git fetch origin` 뒤 `git log origin/main`에 02(PR #24, 30c673d)는 병합됐고 01은 없다. 01은 PR이 없고 형제 워크트리 `01-dev-base-tools`에 커밋이 없다. 티켓 03의 첫 수락 기준과 `Blocked by`가 01의 병합을 요구한다.
- 01이 병합되면 이 PR로 돌아와 병합한다. 그 전에 `git fetch origin` 뒤 `git merge-base --is-ancestor origin/main HEAD`를 보고 뒤처졌으면 main을 합쳐 푸시한다(main의 strict). 병합 뒤 `tools/tidy_checkouts.py`에 병합처 상수(`origin/dev`도 병합처로 본다)가 들어왔는지 본다. 이 PR의 `tidy-checkouts` 문장("도구는 `origin/main`과 `origin/dev`를 둘 다 병합처로 본다")이 그 도구의 01 판에 기대기 때문이다.
- 문서가 가리키는 도구(`tools/base_rule.py`, `check_ticket`의 `base_ref`, `hook_push_behind_main`의 `base_branch`, `tidy_checkouts`의 병합처, `hook_git_main_commit`의 보호 브랜치 둘)는 01이 넣는다. 01이 병합되기 전의 main에서는 이 문서가 앞서간다.
- 그 뒤는 04(`04-dev-branch-create`: dev를 따고 GitHub 설정을 바꾼다. 사용자의 승인을 다시 받는다)다. 05는 04와 agent-os의 `dev-release-pr-step` 병합 뒤에 한다.
- 이어받을 상태: 대기열 `adr-body-rewrite-vs-pointer`(1회차)를 적었다. 사용자 수준 스킬(`git-pr`, `git-pr-merge`, `git-pr-feedback`, `git-branch`)의 main 박힘은 고치지 않았고 고칠지는 사용자가 정한다(티켓 끝 "결과 2").
- 주 체크아웃 미갱신: 루트는 main(11f91c9). 이 세션은 주 체크아웃을 당기지 않는다.
