# harness open-session-env-button 일지 · 2026-11-11

harness 티켓 `.scratch/harness/issues/open-session-env-button.md`를 한 기록이다. 지시문 없이 사용자가 붙여 넣은 요청으로 연 세션(Opus 5.5)이고, 브랜치는 `chore/open-session-env-button`, 작업은 워크트리 `open-session-env-button`에서 했다. agent-os PR 522(인계 열기가 새 세션 화면의 폴더를 환경 버튼으로 고쳐 보낸다)를 이 저장소에 옮겼다. 한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다.

## 한 것

- `tools/open_session.ps1`을 agent-os origin/main 판으로 통째로 바꿨다. sha256이 요청의 값(`246603e6…7d0d7c`)과 같은 것을 `sha256sum`으로 봤다.
- open-session 스킬은 사본이 달라 통째로 옮기지 않았다. agent-os 주 체크아웃의 작업 트리는 origin/main보다 뒤처져 아직 옛 문장이었으므로, PR 522 커밋(`5f7e39ed9`)의 `--word-diff`에서 바뀐 조각을 골라 3단계의 폴더 문장과 오류 갈래, 6단계의 보고 칸을 맞췄다. 처음에는 요청대로 서두 문단을 범위 밖에 뒀으나, 셀프 리뷰 두 축이 서두의 "다르면 멈춘다(3)"가 바뀐 3단계와 어긋난다고 짚어 사용자에게 물었고, 사용자가 "서두도 맞춤"을 골라 함께 맞췄다.
- `tools/sibling_overlap.py`가 고친 두 줄(3단계 24·32행)의 agent-os 일지 인용 넷을 이 저장소에 없는 일지라고 짚어, 도구의 안내대로 코드 스팬으로 감쌌다. 고치지 않은 줄의 인용은 그대로 뒀다.

## 손으로 본 것

- agent-os의 `.scratch/harness/probes/composer_env_menu.ps1 -Leaf rag-engine`을 스크래치패드에 꺼내 돌려, 환경 메뉴에 `rag-engine` 환경(폴더 `C:\project\rag-engine`)과 `agent` 환경이 있는 것을 봤다. 환경 이름이 폴더의 마지막 토막과 같다.
- 같은 프로브의 `-Pick agent`로 앱의 마지막 폴더를 `C:\project\agent`로 둔 뒤, 첫 줄이 `/no-such-skill-for-folder-test`인 프롬프트 파일로 워크트리 사본의 `open_session.ps1 -Action send -Folder C:\project\rag-engine`을 쳤다. 출력은 `folder-fixed=C:\project\agent -> C:\project\rag-engine`, `folder=C:\project\rag-engine`, `held=` 순서였고 세션은 생기지 않았다. `-Folder` 검사(`Get-RepoRoots`)는 워크트리 사본에서도 주 체크아웃 루트를 받는다.
- 프로브를 한 번 더 돌려 마지막 폴더가 `C:\project\rag-engine`인 것을 보고, 새 세션 화면에 남은 시험 입력을 지웠다(`box-after=[]`).
- `uv run pytest tests/tools -q`가 2725 passed(20분). 커밋의 pre-commit도 모두 통과했다.

## 코드 리뷰

`/code-review`(base `1ab024d`, 수정 둘, 미추적 티켓 하나, 커밋 없음).

- 표준 축(sonnet·high): 서두 문단의 잔존(hard), 스크립트 주석이 이 저장소에 없는 프로브·티켓·대기열 번호를 가리킴(hard), 읽은 경로에 `-Folder`가 섞인 갈래를 3단계가 적지 않음(minor), `held=` 길에서 `folder-fixed=`가 보고에서 빠짐(갈래 밟기), 냄새 둘(Data Clumps, Primitive Obsession. 상류 코드라 건드리지 않음).
- 명세 축: 요구 1·2는 맞고 빠진 것과 범위 넘침은 없음. (c)로 서두 문단의 모순과 스크립트 주석의 근거 없음.
- 고친 것: 서두 문단(사용자의 답으로).
- 남긴 것과 이유: 스크립트 주석은 해시를 지키려고 고치지 않고 티켓 Comments에 출처를 적었다. 섞인 경로 갈래와 `held=` 길의 보고는 agent-os 원문과 같은 상태라 티켓 Comments에 남겼다. 냄새는 상류 코드라 뒀다.
- 다시 돌린 명령: 커밋의 pre-commit으로 갈음했고 모두 통과했다.

PR 직전 `coderabbit-review`: CLI 0.7.5, `Seat: not assigned`, `review_completed`, findings 0건. 서브에이전트가 따로 낸 Minor 하나(SKILL.md의 agent-os 일지 인용 열 개 가운데 넷만 코드 스팬)는 남겼다. `sibling_overlap.py`가 바뀐 줄의 인용만 요구하고, 나머지까지 감싸면 agent-os 판과의 차이가 커진다.

## 회고

후보 다섯, 승인 0, 기각 5, 넘김 0. 대기열에 새로 쓰거나 회차를 더한 항목은 없다. `uv run python tools/queue_open_rows.py`(작업 폴더와 `--ref origin/main` 둘 다)의 만료할 항목은 없었다.

1. **요청의 범위("세 군데만")를 글자대로 읽어 같은 파일 서두에 옛 동작이 남았다.** 셀프 리뷰 두 축이 잡았다. 리뷰가 잡도록 둔 기준(`code-review` 두 브리프의 잔존 항목)을 리뷰가 잡은 것이라 회차 셈에서 빼고, 검사로 옮길 꼴도 아니어서 기각이다.
2. **agent-os 주 체크아웃의 작업 트리가 origin/main보다 뒤처져, 요청대로 Read로 연 스킬이 옛 문장이었다.** 결과가 요청과 맞지 않아 PR 커밋의 diff로 돌아갔다. 길은 사용자가 붙여 넣은 요청이 냈고 이 저장소에는 다른 저장소의 판을 옮기는 절차 문서가 없어, 고쳐 쓸 층이 없다. 기각이다.
3. **워크트리 가드와 훅에 걸린 명령 넷.** 한 호출에 묶은 git(앱의 워크트리 가드가 두 번 거부), 다른 체크아웃으로 가는 `cd`(`hook_bash_cd_outside`), `origin/main:<경로>`의 MSYS 경로 변환(훅의 계기), 72자를 넘은 커밋 제목(`hook_bash_commit_msg`)이다. 모두 그 자리에서 막거나 알렸으므로 기각이다.
4. **판정 명령을 파이프로 쳤다(`uv run pytest tests/tools -q 2>&1 | tail -5`).** 훅이 그 자리에서 알렸고, 관련 시험은 파이프 없이 따로 돌렸다. 기각이다. 열린 항목 `gate-pipe-read-status`는 경고가 잘못 뜨는 자리(거짓 양성)를 다루므로 이 일과 다르다.
5. **`tools/sibling_overlap.py`가 고친 줄에 원래 있던 agent-os 일지 인용을 짚었다.** 도구가 제 몫을 한 것이고 도구의 안내대로 코드 스팬으로 감쌌다. 기각이다.

## 다음

- 이 PR(#13) 병합 뒤 새로 열 세션은 없다. 프론티어는 core이고, 남은 `ready-for-agent` 티켓 가운데 08(`feature/08-parsers-isolation`)과 09(`feature/09-search-complete-tools`)는 각자 세션이 맡고 있으며, 10부터는 08·09에 막혀 있다. 08·09가 병합되면 그 세션이 next-session으로 10을 연다.
- 병합 뒤 `send`는 주 체크아웃 사본을 절대 경로로 부르므로, 주 체크아웃을 당긴 뒤(`tidy-checkouts`)에 새 판이 돈다.
