# session-model-fable-5-2: 설계 인터뷰와 명세 지시문의 모델 값을 Fable 5.2로 고친다 · 2026-11-13

search-eval 설계 세션(Fable 5.2 / xhigh, 일지 `2026-11-12-2108-search-eval-design.md`)이 PR #27을 병합한 뒤 같은 세션에서 이어 한 하네스 고침의 기록이다. 티켓은 `.scratch/harness/issues/session-model-fable-5-2.md`, 브랜치는 `chore/session-model-fable-5-2`이고, 작업은 앞 작업의 워크트리 `search-eval-design`에서 `origin/dev`(bf5a0ad)로 새 브랜치를 따서 했다. 계기, 한 것, 실행 확인, 셀프 리뷰, 검증, 다음을 차례로 둔다.

## 계기

- PR #27을 dev에 병합한 뒤(bf5a0ad) `next-session`이 명세 지시문을 냈고, 결정표의 명세 줄대로 "모델" 줄은 `Fable 5.1 / xhigh`였다. `open-session` 3단계의 `tools/open_session.ps1 -Action send`가 `folder-fixed=C:\project\agent -> C:\project\rag-engine` 뒤에 `5초 안에 모델 메뉴의 'Fable 5.1' 을(를) 찾지 못했다.`로 멈췄다. 그 앞에 `restore=필요`가 나왔고, 원래 기본값은 `Sonnet 5.5 / high`였다. 지시문은 새 세션 화면에 남았고, 스킬대로 같은 파일로 다시 돌리지 않고 사람에게 모델과 노력을 골라 보내 달라고 부탁했다.
- 사람이 보낸 세션 `docs/search-eval-spec`은 `get_session`에서 `model`이 `claude-fable-5-2`, `effort`가 `medium`이었다(손으로 봤다, 2026-11-13 01:22 무렵). 지시문의 "모델" 줄은 `xhigh`였으므로 노력이 지시문과 다르다. `open-session` 4는 다르면 사람에게 알리라고 하고 그 스킬의 "하지 않는 것" 표는 보낸 뒤 `set_session_model`·`set_session_effort`로 맞추지 않는다고 적으므로, 덮지 않고 사용자에게 알린다.
- 턴을 끝내며 결정표의 모델 값을 메뉴에 있는 값으로 고칠지를 물었고, 사용자가 답했다(선택지의 라벨이고 설명은 없었다).

  > 사용자: "5.2로 고치기"

- 결정표의 값이 낡은 경위는 일지로만 읽었다. 2026-11-10의 명세 세션은 `next-session` 지시문이 `Fable 5.1 / xhigh`로 열었다(일지 `2026-11-10-0118-core-spec.md` 3행과 19행). 지시문 없이 연 세션의 일지는 2026-11-11 오전 것이 Fable 5.1을, 같은 날 오후 것이 Fable 5.2를 적는다(`2026-11-11-0929-core-get-document-text-window.md` 3행, `2026-11-11-1534-doc-permission-list-filter.md` 3행). 그 사이에 앱의 모델 메뉴에서 이름이 바뀌었고 결정표가 따라가지 못한 것으로 어림한다. 그때의 메뉴를 본 기록은 없다.

## 한 것

- `.claude/skills/next-session/SKILL.md` 결정표의 설계 인터뷰 줄, 명세 줄, "이어서" 줄의 모델 칸과 `.claude/skills/next-session/directive.md` 2의 잇는 지시문 문장에서 `Fable 5.1 / xhigh`를 `Fable 5.2 / xhigh`로 고쳤다. 네 자리이고, 값 밖에 더한 것은 아래 셋째 줄의 문장 하나다.
- `directive.md` 2의 사다리 문장("설계 인터뷰·명세의 Fable 칸")은 판 번호가 없어 그대로 두었다.
- 같은 `directive.md` 2의 "칸의 값과 바꾸는 절차의 근거는 agent-os ADR 0029다" 뒤에 Fable 칸의 판 번호는 앱의 모델 메뉴에 있는 이름을 따른다는 문장을 더했다(셀프 리뷰 명세 축의 지적). 그 ADR의 이력 "2026-10-31 설계 인터뷰와 명세 칸은 측정 없이 사용자의 결정으로 Fable 5.1 / xhigh로 바꾼다"가 5.1을 적고, 같은 이력이 그때의 모델 메뉴에 RadioButton `Fable 5.1`이 있었다고 적는다(agent-os 체크아웃 `C:\project\agent`의 작업 트리에서 `docs/adr/0029-session-model-is-picked-before-send.md`의 378·385·412행을 Grep으로 읽었다).
- 코드와 시험은 바꾸지 않았다. `tools/open_session.ps1`의 `Read-ModelLine`은 `모델:` 줄에서 `/` 앞의 글을 이름으로 읽고 `Find-MenuRadio`가 `Test-NameShows`로 메뉴의 라디오 항목과 대 볼 뿐이라(코드를 읽었다, origin/dev bf5a0ad) 이름의 목록이 따로 없다. `tools/`와 `tests/`의 `*.py`에는 `Fable`, `Sonnet 5.5`, `Opus 5.5`, `xhigh`가 한 번도 나오지 않는다(Grep으로 손으로 봤다).
- 잔존: `git grep -n -I -i --untracked "fable" -- . ":(exclude)docs/journal"`에서 옛 값 `Fable 5.1`이 남은 자리는 이 티켓(경위를 적은 문장과 수용 기준)뿐이다. 일지 세 편(네 줄)의 `Fable 5.1` 언급은 그때의 기록이라 고치지 않았다(`git grep -n -I "Fable" -- docs/journal`).
- `uv run python tools/sibling_overlap.py`는 0으로 끝났고, 형제 워크트리 `05-dev-release-pr-step`이 같은 파일 `.claude/skills/next-session/SKILL.md`를 고치고 있다고 알렸다. 그 브랜치에 커밋된 변경은 없어(`git diff origin/dev...feature/05-dev-release-pr-step -- .claude/skills/next-session/SKILL.md`가 비었다) 어느 줄인지는 보지 못했다. 나중에 병합하는 쪽이 글자 충돌을 푼다.

## 실행 확인

스크립트가 메뉴에서 `Fable 5.2`를 찾는지를 `defaults` 동작으로 손으로 돌려 봤다(2026-11-13 01:26~01:27, 워크트리 사본의 `tools/open_session.ps1`. 주 체크아웃이 가리키는 커밋 11f91c9의 사본과 내용이 같다. `git diff --stat 11f91c9 origin/dev`에 이 파일이 없다. 주 체크아웃의 작업 트리는 보지 않았다). `Select-ComposerModelItem`은 모델 버튼이 이미 그 모델을 보이면 메뉴를 열지 않으므로, 먼저 다른 모델로 옮긴 뒤에 골랐다.

1. `pwsh -NoProfile -File tools/open_session.ps1 -Action defaults -Model 'Sonnet 5.5' -Effort high` → `model=Sonnet 5.5 원래 Fable 5.2`, `effort=high 원래 medium`, `defaults=Sonnet 5.5 / high`. 새 세션 화면의 기본값이 사람이 손으로 고른 값(`Fable 5.2`, `medium`)으로 남아 있었다.
2. `pwsh -NoProfile -File tools/open_session.ps1 -Action defaults -Model 'Fable 5.2' -Effort xhigh` → `model=Fable 5.2 원래 Sonnet 5.5`, `effort=xhigh 원래 high`, `defaults=Fable 5.2 / xhigh`. 멈췄던 길(모델 메뉴에서 이름 찾기)이 이 이름으로 지나갔고, 고른 뒤 모델 버튼이 그 값을 보이는 것까지 스크립트가 확인했다.
3. 1의 명령을 한 번 더 → `model=Sonnet 5.5 원래 Fable 5.2`, `effort=high 원래 xhigh`, `defaults=Sonnet 5.5 / high`. 새 세션 화면의 기본값은 멈춘 열기 전의 값(`Sonnet 5.5 / high`)으로 돌아왔다. 멈춘 열기가 사람에게 남긴 `restore=필요`의 명령이 이것이라, 그 일도 이것으로 끝났다.

`send`로 지시문을 실제로 보내는 길은 돌리지 않았다. 세션이 하나 생기기 때문이다. `send`와 `defaults`는 모델과 노력을 같은 함수(`Set-ComposerModel`)로 고른다(코드를 읽었다).

## 셀프 리뷰

`code-review` 두 축. base `bf5a0ad`, 커밋 0, 바뀐 추적 파일 둘(네 줄)과 미추적 둘(티켓, 이 일지). 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다. 두 축에 `tools/open_session.ps1`을 실행하지 말라고 일렀고, 표준 축은 순수 함수 `Read-ModelLine`과 `Test-NameShows`만 떼어 불러 봤다.

- 표준 축: 하드 위반 없음, Minor 셋, Nit 둘, 주장 검증에서 덧붙임 하나.
  - Minor(냄새, 판단). 같은 값 `Fable 5.2 / xhigh`가 네 곳에 흩어져 있어 이름이 바뀔 때마다 네 곳을 고쳐야 한다. → 남겼다. 값을 한 곳으로 모으는 것은 결정표와 `directive.md` 2의 구조를 바꾸는 일이라 이 티켓의 범위 밖이다. 회고 후보로 넘긴다.
  - Minor(갈래). 주 체크아웃(11f91c9)과 형제 워크트리 `05-dev-release-pr-step`, `search-eval-spec`(bf5a0ad)의 스킬 사본은 옛 값을 적는다. 그 사본으로 설계 인터뷰나 명세 지시문을 내는 세션은 같은 자리에서 멈춘다. → 적었다. 이 PR은 다른 체크아웃을 바꾸지 못하므로 아래 "다음"과 PR 본문의 남긴 위험에 그 갈래와 사람의 길(지시문의 모델 줄을 `Fable 5.2 / xhigh`로 맞춰 보낸다)을 적는다. 리뷰는 사람이 되돌리기를 세 번 되풀이해야 한다고 적었지만, 이 일지의 세 번은 메뉴를 찾는 길을 지나려고 일부러 옮긴 것이고 멈춘 열기 뒤에 사람이 칠 것은 `restore=필요` 줄의 명령 한 번이다.
  - Minor(갈래). 옛 "이어서" 줄로 열려 모델 줄이 `Fable 5.1 / xhigh`인 구현 세션이 끊기면 `directive.md` 2가 그 줄의 값을 그대로 이어 옛 값이 다음 지시문으로 넘어간다. → 남겼다. 그런 세션을 알지 못한다. 이 세션이 낸 Fable 값의 지시문은 명세 세션 `docs/search-eval-spec`의 것 하나이고, 명세를 잇는 지시문은 줄의 값이 아니라 `directive.md` 2의 문장에서 값을 읽으므로 위 사본 갈래에 든다. 다른 세션의 지시문은 보지 않았다. 막으려면 지침 문장을 더해야 하는데 교정 루프의 문턱 전이다.
  - Nit. 티켓이 "메뉴에 `Fable 5.1` 항목이 없어"라고 적었는데 본 것은 스크립트가 5초 안에 찾지 못했다는 것이다. → 고쳤다. 티켓의 문장을 스크립트가 그 이름의 항목을 찾지 못하고 멈췄다는 것으로 바꿨다.
  - Nit. 티켓의 "이름을 그대로 찾고"는 `Test-NameShows`가 이름 뒤의 공백과 덧붙임도 받는 것과 어긋난다. → 고쳤다. 티켓과 커밋 메시지의 문장을 그 판정대로 적었다.
  - 덧붙임. "주 체크아웃 사본과 내용이 같다"의 근거가 커밋 비교이고 주 체크아웃의 작업 트리는 본 것이 아니다. → 고쳤다. 실행 확인 절에 그렇게 적었다.
  - 주장 검증에서 맞다고 본 것: 다른 일지의 행 번호와 내용, 일지 세 편(네 줄), 다섯째 자리 없음(`git grep -i --untracked fable`, `.gitignore` 대상은 보지 못했다), `*.py`에 모델 이름 없음, 스크립트 서술(모델 이름의 목록 없음, `Select-ComposerModelItem`의 이른 반환, `send`와 `defaults`가 같은 `Set-ComposerModel`), 이름 규칙(`Fable 5.2` → `claude-fable-5-2`), 티켓 서식과 브랜치 stem과 일지 파일 이름. 실행 확인의 출력 세 번은 다시 돌릴 수 없어 확인하지 못했고, 근거의 종류는 맞게 갈렸다고 봤다.
- 명세 축: 빠진 요구 없음, 범위 넘침 없음(`git diff --word-diff=porcelain`에서 바뀐 글자가 `5.1`에서 `5.2`로 네 번뿐이었다. 아래 첫 지적을 반영하기 전의 판이다), Minor 둘, Nit 셋.
  - Minor. 고치지 않은 `directive.md` 2의 "칸의 값과 바꾸는 절차의 근거는 agent-os ADR 0029다"가 Fable 칸에서 어긋난다. 그 ADR은 `Fable 5.1 / xhigh`를 적고, 옛 값 grep으로는 이 문장이 잡히지 않는다. → 고쳤다. 그 ADR을 직접 열어 확인한 뒤(위 "한 것"의 셋째 줄) 그 문장 뒤에 Fable 칸의 판 번호는 메뉴의 이름을 따른다는 문장을 더하고, 티켓의 What to build에 그 일을 적었다. 리뷰가 덧붙인 agent-os 사본의 결정표(네 자리가 5.1)는 이 저장소 밖이라 고치지 않고 사용자에게 알린다.
  - Minor(diff의 결함이 아니라 전파의 틈). 병합 뒤에도 주 체크아웃(11f91c9)의 사본과 bf5a0ad에서 딴 워크트리의 사본은 옛 값을 낸다. 명세 세션 `docs/search-eval-spec`이 명세를 끊으면 dev를 합치기 전에는 5.1을 낸다. → 적었다. 표준 축의 둘째 지적과 같은 갈래이고 아래 "다음"에 한 줄을 둔다.
  - Nit. 티켓의 "메뉴에 `Fable 5.1` 항목이 없어". → 고쳤다(표준 축의 넷째 지적과 같다).
  - Nit. 이 일지가 `open-session` 4대로 `set_session_effort`로 덮지 않는다고 적었는데 4단계는 `set_session_model`만 적고 `set_session_effort`는 "하지 않는 것" 표에 있다. → 고쳤다. 계기 절의 문장을 두 자리를 갈라 적었다.
  - Nit. 수용 기준 둘째 줄의 명령에 `--untracked`가 없어 커밋 전에는 0건이다. → 남겼다. 티켓이 추적되면 그 명령 그대로 맞으므로 스테이징한 뒤 다시 돌려 아래 "검증"에 적는다.
  - 주장 검증에서 맞다고 본 것: 네 자리와 다섯째 자리 없음(`fable`, `claude-fable`, `xhigh`, `Sonnet|Opus`로 일지 밖을 찾았다), 모델 이름의 목록 없음(AST로 `Read-ModelLine`·`Get-EffortSteps`·`Test-NameShows`의 글만 뽑아 불렀고 `Read-ModelLine`은 없는 이름 `Nonexistent 9.9`도 받았다), 오류문 인용(`Wait-For`와 `Select-MenuRadio`의 글을 합친 것과 같다), `send`만 지나는 모델 관련 코드 셋(지시문 전체의 `Read-ModelLine`, 모델 고르기 앞의 `Repair-ShownFolder`, 보낸 뒤의 `Restore-DraftDefaults`)이 모두 모델 이름에 기대지 않는 것, 사다리 갈래(5.2도 사다리 밖이라 동작이 그대로다), 앞 일지에 이 고침을 미룬 미래형 문장이 없는 것.
- 반영으로 새로 쓴 사실 문장(PR 직전 리뷰와 PR 봇이 겨냥할 것): `directive.md` 2의 "Fable 칸의 판 번호는 앱의 모델 메뉴에 있는 이름을 따른다(그 ADR은 5.1로 적는다. harness 티켓 `session-model-fable-5-2`)", 티켓의 "스크립트는 지시문의 `모델:` 줄에 적힌 이름으로 메뉴의 항목을 찾고(이름이 같거나 이름 뒤에 공백과 덧붙임이 오는 항목이다. `Test-NameShows`)".
- 다시 돌린 명령: 문서 검사는 아래 "검증"에 적는다. 손으로 치는 다섯은 커밋의 pre-commit으로 갈음한다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트(Sonnet)가 CodeRabbit CLI 0.7.5를 한 번 돌렸다. 명령은 `coderabbit review --agent --include-untracked --base-commit bf5a0ad30440cc0d1fdb24e638ac008e2949d9b6`이고, 리뷰는 끝까지 돌아(`review_completed`) 지적이 0건이었다. 좌석은 `Seat: not assigned`(`Plan: Free`)였다. 리뷰한 파일은 넷(`.claude/skills/next-session/SKILL.md`, `.claude/skills/next-session/directive.md`, 티켓, 이 일지)이고 dev의 다른 커밋은 범위에 들지 않았다. 고친 것도 남긴 것도 없다.

CLI가 보지 못한 것: 리뷰를 띄운 뒤에 쓴 대기열 항목 `.scratch/retro-queue/model-menu-name-drift.md`와 이 일지의 회고, 검증, 다음 절이다. CLI에는 밀 주장을 넘기는 인자가 없어 셀프 리뷰 반영으로 새로 쓴 문장 둘도 따로 겨냥하게 하지 못했다. 이 몫은 PR 봇(CodeRabbit PR 리뷰, claude-review)이 본다.

## 회고

낸 후보 넷. 승인 하나, 기각 셋, 넘김 없음.

1. 결정표가 적은 모델 이름이 앱의 모델 메뉴에서 바뀌자 세션 열기가 멈췄다. → 승인.
   - 사건: 위 "계기"의 멈춘 열기다. 사람이 지시문을 손으로 보냈고, 세션은 지시문의 `xhigh`가 아닌 `medium`으로 열렸다. 멈춘 열기의 오류문은 찾던 이름만 적고 메뉴에 있는 이름을 적지 않는다.
   - 층: 저장소의 검사와 CI는 앱의 메뉴를 보지 못한다. 그 메뉴를 읽는 `tools/open_session.ps1`이 가장 높은 층이다.
   - 되돌림: PR 하나로 되돌릴 수 있다.
   - 간 자리: 값을 고치는 것은 고침이라 이 PR이 반영했다(값은 사용자가 정했다). 오류문에 메뉴의 항목 이름을 싣는 것은 더하는 것이라 대기열 `model-menu-name-drift`에 1회차로 두었다. 같은 일을 다룬 항목은 없었다(`uv run python tools/queue_open_rows.py --search open_session --search 모델.메뉴 --search next-session/SKILL.md --search Fable`에 맞은 것은 다른 일인 `harness-feature-off-plan` 하나였다).
2. 병합 뒤에도 주 체크아웃과 먼저 딴 워크트리의 스킬 사본이 옛 값을 낸다(셀프 리뷰 두 축의 Minor). → 기각. 사건 없이 떠올린 갈래다. 이번에 멈춘 것은 사본이 낡아서가 아니라 dev의 값이 낡아서였다. 아래 "다음"에 적는다.
3. 이 일지의 첫 판이 근거를 열지 않은 문장(스크립트로 설계·명세 지시문을 연 것이 이번이 처음이라는 것)을 적었다. → 기각. 리뷰에 넘기기 전에 이 세션이 다른 일지를 대조하다 틀린 것을 알고 고쳤고, 든 비용이 없다.
4. 커밋 시도 둘의 pre-commit이 부하에서만 빨간 시간 시험 하나씩으로 막혔다. 첫 시도는 `tests/adapters/test_parse_runner.py`의 멈춘 자식 시험, 둘째 시도는 `tests/test_serve_command.py`의 기동 30초 시험이고, 둘 다 따로 돌리니 초록이었다(아래 "검증"). → 기각, 일지에만. 부하에서만 빨간 시간 시험은 닫힌 항목 `token-expiry-test-load-margin`이 받아들여 닫은 종류라 새 사례를 항목으로 잇지 않는다(retro 5단계). 든 비용은 pre-commit 두 바퀴(약 13분과 18분)와 그 사이에 다른 러너가 없는 때를 기다린 35분이다. 다시 열지는 사용자가 정한다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev`를 붙인 것 모두 만료할 항목이 없었다.

## 검증

- 문서 검사(커밋 전, 손으로 돌렸다): `uv run python tools/check_md_tables.py`와 `uv run python tools/check_line_separators.py`(바뀐 넷)는 출력 없이 0, `uv run python tools/check_instructions.py`는 0, `uv run python tools/sibling_overlap.py`는 0(함께 고친 파일 알림은 위 "한 것"), `uv run python tools/check_commit_msg.py <메시지 파일>`은 0이었다. `uv run python tools/check_quotes.py --all-lines`(새 둘)는 첫 판에서 이 세션의 질문을 따옴표로 옮긴 한 건을 경고했고, 따옴표를 떼고 풀어 적었다. 셀프 리뷰를 반영한 뒤 다시 돌리니 agent-os ADR 0029의 이력 제목을 옮긴 인용 한 건을 경고했다. 다른 저장소의 원문을 글자 그대로 옮긴 것이라 두었다(이 검사는 경고만 한다).
- 잔존: 스테이징한 뒤 `git grep -n -I -o "Fable 5.1" -- . ":(exclude)docs/journal"`은 티켓의 3행(두 번)과 10행만 냈다. 새 대기열 항목은 `uv run python tools/queue_open_rows.py --search model-menu-name-drift`가 열림 1회차로 읽었다.
- 손으로 치는 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)은 커밋의 pre-commit으로 갈음한다. 결과는 PR 본문에 적는다.
- 첫 커밋 시도는 pre-commit에서 멈춰 커밋이 만들어지지 않았다. 검사 러너의 pytest가 `1 failed, 3824 passed in 744.21s (0:12:24)`였다. 러너의 나머지 열(test-db, check-ticket, zizmor, check-instructions, check-type-escapes, lint-imports, pyright-linux, pyright, run-hooks)과 표, 줄 구분자, 변이 표 훅은 Passed였고, ruff 두 훅은 바뀐 파이썬 파일이 없어 건너뛰었다. 실패한 시험은 `tests/adapters/test_parse_runner.py`의 `test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다`다(Windows 기대 `parse_failed`에 `parse_timeout`이 왔다). 이 브랜치는 파이썬 파일을 바꾸지 않았다. 그 시험만 따로 돌린 `uv run pytest tests/adapters/test_parse_runner.py -q -p no:cacheprovider -k 멈춘_자식`은 `1 passed, 35 deselected in 3.32s`였다. 실패를 본 직후의 프로세스 목록에는 다른 세션의 검사 러너와 pytest가 함께 돌고 있었다(손으로 봤다. 이 저장소의 워크트리 `05-dev-release-pr-step`와 agent-os 저장소의 워크트리 둘이다). 시험은 고치지 않았다. 다른 러너가 없는 때를 02:14부터 02:49까지 기다렸으나(15~20초마다 프로세스 목록을 세는 스크립트를 돌렸다) agent-os 저장소의 세션들이 러너를 잇달아 돌려 빈 때가 없었다. 02:49에 `tools/run_checks.py` 프로세스가 넷(러너 둘로 읽었다) 남은 채로 커밋을 다시 띄웠다.
- 둘째 커밋 시도도 pre-commit에서 멈췄고, 빨간 것은 다른 시험 하나였다. 검사 러너의 pytest가 `1 failed, 3824 passed in 1065.54s (0:17:45)`였다(러너의 나머지 열과 표, 줄 구분자, 변이 표 훅은 Passed). 실패한 시험은 `tests/test_serve_command.py`의 `test_serve가_뜨면_JSON_Lines만_남기고_접근_로그에_쿼리_문자열을_싣지_않는다`이고 실패문은 `serve가 30초 안에 뜨지 않았다`다. 첫 시도에서 빨갛던 `test_parse_runner`의 시험은 이번에 통과했다. 그 파일만 따로 돌린 `uv run pytest tests/test_serve_command.py -q -p no:cacheprovider`는 `2 passed in 10.88s`였다(`RAG_TEST_DATABASE_URL`을 `compose.test.yml`의 값으로 주었다). 따로 돌린 때에도 다른 세션의 러너 둘과 pytest가 돌고 있었다(03:09에 손으로 본 프로세스 목록. CPU 사용률은 77%였다). core 12 일지가 적은 `serve` 기동 30초 시험의 부하 민감성과 같은 사례다. 시험은 고치지 않았다.

## 다음

- 주 체크아웃(11f91c9)과 bf5a0ad에서 딴 워크트리(`05-dev-release-pr-step`, `search-eval-spec`)의 스킬 사본은 이 PR을 당기거나 합치기 전까지 `Fable 5.1 / xhigh`를 낸다. 그 사본으로 낸 설계 인터뷰나 명세 지시문이 모델 오류로 멈추면, 사람이 새 세션 화면에서 모델 `Fable 5.2`와 노력 `엑스트라`(xhigh)를 골라 보내고 `restore=필요` 줄의 명령을 친다. 명세 세션 `docs/search-eval-spec`이 명세를 끊고 잇는 지시문을 낼 때가 그 갈래다.
- 명세 세션 `docs/search-eval-spec`은 `medium`으로 돌고 있다. 노력을 올릴지는 사용자가 정한다.
- agent-os 저장소의 같은 결정표도 `Fable 5.1 / xhigh`를 적는다(셀프 리뷰 명세 축이 그 사본을 Grep으로 읽었다). 이 저장소 밖이라 고치지 않았다.
- 새 세션 화면의 기본값은 `Sonnet 5.5 / high`로 돌아와 있다. 멈춘 열기가 남긴 `restore=필요`는 끝났다.
