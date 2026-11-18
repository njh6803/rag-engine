# glossary-harness-small-names: 회고와 대기열이 쓰는 작은 이름 셋을 agent-os의 결정에 맞춘다(여러 곳에서 나는 같은 결함, 다시 올라온 항목, 추가 기준 횟수) · 2026-11-18

앞 세션(일지 `2026-11-18-1444-glossary-release-names.md`)이 PR 66을 병합하고 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-harness-small-names.md`, 브랜치는 `chore/glossary-harness-small-names`이고, 새 워크트리 `glossary-harness-small-names`에서 `origin/dev`(bc31442)로 브랜치를 따서 했다. 용어집의 이름을 agent-os의 결정에 맞추는 일(받은 지시문의 원문 `.scratch/glossary-names-input.md`. 아래에서 "받은 지시문"은 이 글이다)의 둘째 PR이고, 받은 지시문 5-2의 차례 1이다. 계기, 세션을 열며 한 정리, 물은 것과 사용자의 답, 앞 PR이 넘긴 것, 한 것, 바꾸지 않고 남긴 것, 옛 이름의 잔존, 검증을 차례로 두고, 그 뒤의 리뷰와 회고는 한 차례씩 덧붙인다.

## 계기

사용자가 아래 지시문을 첫 메시지로 넣어 이 세션을 열었다. 글자 그대로다.

```
용어집의 작은 하네스 이름 묶음(끝이 열린 결함 종류, 이은 항목, 더하는 문턱)을 agent-os의 결정에 맞추는 PR을 티켓 .scratch/harness/issues/glossary-harness-small-names.md로 쓰고 한다

다음 작업: 받는 세션이 쓸 .scratch/harness/issues/glossary-harness-small-names.md. 받은 지시문 5-2의 차례 1이다. 세 이름의 새 이름을 사용자에게 선택 화면으로 묻고, 고른 이름으로 용어집과 살아 있는 글을 바꾼다
다음 단계: 구현
어디서: 새 세션. 결정표의 이어서 줄은 이 세션이지만, 앞 세션의 요청 범위가 PR 66의 병합까지였고 컨텍스트가 한 번 압축되어 새 세션으로 연다. Docker가 켜진 로컬 세션에서 연다. 주 체크아웃 미갱신이라 Skill 도구로 tidy-checkouts를 먼저 돌고(그 스킬이 사람에게 넘기는 것은 보고만 하고 답을 기다리지 않는다) 그 뒤 주 체크아웃에서 브랜치를 따지 않고 EnterWorktree(name은 브랜치의 마지막 토막)로 새 워크트리에 먼저 들어가 거기서 브랜치를 바꾼다
시작 프롬프트: 용어집의 작은 하네스 이름 묶음(끝이 열린 결함 종류, 이은 항목, 더하는 문턱)을 agent-os의 결정에 맞추는 PR을 티켓 .scratch/harness/issues/glossary-harness-small-names.md로 쓰고 한다
브랜치: chore/glossary-harness-small-names
모델: Sonnet 5.5 / high
읽을 것: .scratch/glossary-names-input.md(받은 지시문의 원문. 1절의 세 이름과 5절의 바꾸는 길), docs/journal/2026-11-18-1444-glossary-release-names.md의 "다음"과 "물은 것과 사용자의 답"(앞 PR이 이름을 물은 방식), docs/agents/issue-tracker.md
이어받을 상태: 주 체크아웃 루트의 추적하지 않는 로그 파일 둘(.scratch_li.log, .scratch_pyr.log)은 2026-11-12부터 있었고 만든 세션을 가리지 못했다. 그 때문에 tidy-checkouts가 루트를 당기지 못하며, 사용자에게 알렸다. PR 66 claude-review 둘째 회차의 Nit 하나를 이 티켓에 넘겼다. 용어집 배포 파일 묶음의 피할 말 "릴리스 자산"을 "GitHub 릴리스 자산"으로 맞출지 본다. 같은 회차에서 사용자는 출시 후보의 피할 말에 더한 "릴리스 후보"를 그대로 두기로 골랐다("그대로 둔다 (Recommended)"). 이 답은 PR 66 코멘트에만 있으니 이 티켓의 일지에 옮긴다
확인할 선행 조건: 주 체크아웃 미갱신: 루트는 dev. 병합은 이 워크트리 사본의 next-session merge.md(없으면 SKILL.md)의 "워크트리에서 병합할 때"를 Read로 열어 따른다
이번 요청 범위: PR과 병합까지
```

이 일은 retro가 승인한 대기열 항목이 아니라 사용자의 직접 지시다. 티켓의 대기열 줄에는 앞 티켓처럼 `glossary-plain-names-left`를 적었다(그 항목은 이름을 바꾸는 일 전체를 가리킨다).

## 세션을 열며 한 정리

지시문대로 이 세션의 제목을 브랜치 이름으로 바꾸고(`set_session_title`) `tidy-checkouts` 스킬을 먼저 돌렸다. 이 세션은 주 체크아웃(`C:\project\rag-engine`)에서 열렸고 `git fetch origin`을 쳤다.

- 주 체크아웃은 당기지 못했다. 루트는 dev이고 `HEAD`는 6957194, `origin/dev`는 bc31442이다. 원격에 없는 로컬 커밋은 0개다. 그런데 `git status --porcelain`에 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 나와 깨끗하지 않았다. 스킬의 "루트 브랜치인데 깨끗하지 않다" 갈래라 건드리지 않았다. 앞 일지 "다음"이 사용자에게 알렸다고 적은 그 파일이다.
- 지운 것은 로컬 브랜치 `worktree-glossary-release-names` 하나다(커밋이 모두 `origin/main`이나 `origin/dev`에 있었다).
- 남긴 워크트리와 `judge`가 낸 이유는 다음과 같다. `05-full-run-rerank`는 그 폴더를 작업 디렉터리로 쥔 프로세스(tail.exe, grep.exe, cut.exe)가 있다. `10-public-docs-questions`는 바뀐 파일이 있다. `13-first-judge-run`은 세션 `local_a6780d9a-3397-4c26-babc-619f7a2ab4e6`의 python.exe 열둘이 쥐고 있다. `16-search-latency-probe-f30c20`과 `relaxed-grothendieck-e892b9`는 앱의 표지가 있어 앱의 정리에 맡긴다. `glossary-release-names`와 `release-image`는 그 브랜치가 제목인 세션이 돌고 있다. `release-image-spec`과 `release-search-eval`은 병합된 PR이 없다.
- 사람에게 넘긴 것은 워크트리 `14-reindex-version-switch` 하나다. 병합된 PR의 머리와 브랜치 끝이 다르다. 앞 세션도 같은 것을 넘겼고, 지시문대로 보고만 하고 답을 기다리지 않았다.
- 휴지통은 비우지 못했다. `empty-trash`가 종료 코드 1로 끝났고 `.venv` 폴더 일곱이 남았다(앞 세션과 같은 일곱). 모두 `.pyd` 파일 하나에서 접근이 거부됐다(WinError 5). 다음 정리가 다시 본다.

그 뒤 `EnterWorktree`(name `glossary-harness-small-names`)로 새 워크트리에 들어갔다. 워크트리의 시작 커밋은 bc31442(`origin/dev`)이었고, `git switch -c chore/glossary-harness-small-names origin/dev`로 브랜치를 바꾸었다. 이 명령은 `origin/dev`를 추적하는 브랜치를 만들어 `git branch --unset-upstream`으로 추적을 끊었다(그대로 두면 푸시가 dev로 갈 수 있다). `EnterWorktree`가 만든 브랜치 `worktree-glossary-harness-small-names`는 지웠다.

## 물은 것과 사용자의 답

티켓을 쓰기 전에 선택 화면을 한 번 올렸다(질문 셋). 받은 지시문 1절은 이 세 이름을 사용자에게 다시 묻지 않고 한다고 적었지만, 이 세션의 지시문이 세 이름의 새 이름을 사용자에게 선택 화면으로 묻고 바꾸라고 적었으므로 물었다. 화면을 올리기 전에 한 일은 둘이다.

- 옛 이름이 쓰인 곳을 Grep으로 셌다. 일지, 받은 지시문의 원문, 닫힌 대기열 항목 같은 기록은 뺐다. 선택지의 "바뀌는 곳"은 이 수다. 사용자가 받은 지시문에서 본 어림(끝이 열린 결함 종류 4개 파일 4곳, 이은 항목 2개 파일 4곳)은 아래 "선택 화면에 보인 수와 실제로 바뀐 수"에서 다시 견준다.
- 새 이름 후보는 받은 지시문 1-1이 적은 것(여러 곳에서 나는 같은 결함, 다시 올라온 항목, 추가 기준 횟수)을 첫째로 두고, 이 저장소의 문장에 넣어 본 대안을 더했다.

아래의 질문, 선택지, 설명은 이 세션에서 올린 글자 그대로다. `> 사용자:` 줄이 답이다.

1. 질문(머리 "결함 종류"): 같은 종류의 결함이 사례마다 다른 자리에서 나올 때 쓰는 항목 이름(지금은 '끝이 열린 결함 종류')을 앞으로 무엇이라고 부를까요? 이 항목은 세 번째 사례부터 사례를 고치지 않고 종류 전체를 없애거나 받아들여 닫습니다.

   > 사용자: "여러 곳에서 나는 같은 결함 (Recommended)"

   - 첫째 선택지 "여러 곳에서 나는 같은 결함 (Recommended)". 설명: agent-os에서 고른 이름과 같습니다. 문장에 넣으면 '여러 곳에서 나는 같은 결함은 세 번째 사례부터 사례를 고치지 않는다'가 됩니다. 걸리는 점: 이름이 길어지고, 닫을 때의 '끝이 열린 종류의 닫기' 같은 줄임말은 '같은 결함의 닫기'로 풀어 써야 합니다. 바뀌는 곳: 살아 있는 파일 4개입니다(retro 스킬 1곳, 열린 대기열 항목 3개 각 1곳).
   - 둘째 선택지 "되풀이되는 결함 종류". 설명: 더 짧고 사람들이 흔히 쓰는 말입니다. 문장에 넣으면 '되풀이되는 결함 종류는 세 번째 사례부터…'가 됩니다. 걸리는 점: agent-os의 이름과 달라지고, 같은 스킬 안에 있는 항목 종류 '같은 실수의 반복'과 낱말이 겹쳐 둘이 같은 것으로 읽힐 수 있습니다. 바뀌는 파일은 첫째 선택지와 같습니다.
   - 셋째 선택지 "지금 이름 그대로". 설명: 바뀌는 파일이 없습니다. 걸리는 점: '끝이 열린'이 무슨 뜻인지 처음 보는 사람이 바로 알기 어렵고, agent-os와 이름이 달라집니다.

2. 질문(머리 "이은 항목"): 만료되었거나 닫힌 개선 항목에 적힌 것과 같은 실수가 또 나서, 회차를 이어 세며 새로 적은 항목 이름(지금은 '이은 항목')을 무엇이라고 부를까요?

   > 사용자: "다시 올라온 항목 (Recommended)"

   - 첫째 선택지 "다시 올라온 항목 (Recommended)". 설명: agent-os에서 고른 이름과 같습니다. 문장에 넣으면 '<식별자>의 k회차로 다시 올라온 항목을 한 번 더 찾는다'가 됩니다. 걸리는 점: 같은 스킬에 '회차를 잇는다', '새 항목이 이을 때' 같은 동작 표현이 남아서, 이름은 '다시 올라온'이고 동작은 '잇는다'로 낱말이 갈립니다. 이 동작 표현은 이번에 바꾸지 않습니다. 바뀌는 곳: retro 스킬 1개 파일 2곳입니다(받은 지시문은 2개 파일 4곳으로 어림했고, 제가 다시 센 값이 이것입니다).
   - 둘째 선택지 "이어 센 항목". 설명: '회차를 이어 센다'는 동작과 낱말이 맞아 읽기 쉽습니다. 문장에 넣으면 '<식별자>의 k회차로 이어 센 항목을 한 번 더 찾는다'가 됩니다. 걸리는 점: agent-os의 이름과 달라집니다. 바뀌는 파일은 첫째 선택지와 같습니다.
   - 셋째 선택지 "지금 이름 그대로". 설명: 바뀌는 파일이 없습니다. 걸리는 점: '이은'만 보면 무엇을 이었는지 알 수 없고 agent-os와 이름이 달라집니다.

3. 질문(머리 "더하는 문턱"): 같은 실수가 몇 번째 났을 때부터 새 검사나 지침을 더해도 되는지 정한 횟수(지금은 '문턱'이라고 줄여 부르는 '더하는 문턱', 곧 다섯 번째)를 무엇이라고 부를까요?

   > 사용자: "추가 기준 횟수 (Recommended)"

   - 첫째 선택지 "추가 기준 횟수 (Recommended)". 설명: agent-os에서 고른 이름이고, 줄여 쓴 '문턱'도 이 이름으로 바꿉니다. 문장에 넣으면 '새 훅·검사가 추가 기준 횟수에 닿으면 훅 보고를 먼저 돌린다', '추가 기준 횟수를 지나기 전에는 대기열에서 회차를 센다'가 됩니다. 걸리는 점: 같은 스킬에 '승인 기준', '리뷰의 기준' 같은 다른 '기준'이 있어 겹쳐 읽힐 수 있습니다. 세션 컨텍스트의 '문턱(20만 토큰)'과 검사 도구의 '문턱'(예: 한국어 비율)은 다른 뜻이라 그대로 둡니다. 바뀌는 곳: retro 스킬 4곳, 검사 러너 도구의 주석 1곳, 열린 대기열 항목 약 6개입니다(항목 수는 어림이고, 일지에 다시 센 값을 적습니다).
   - 둘째 선택지 "더하는 횟수". 설명: '더하는 것'(새 훅·검사·지침을 더하는 일)이라는 retro의 분류와 낱말이 맞습니다. 문장에 넣으면 '새 훅·검사가 더하는 횟수에 닿으면', '더하는 횟수를 지나기 전에는 회차를 센다'가 됩니다. 걸리는 점: '더하는 것'의 종류와 '더하는 횟수'가 한 문장에 나오면 뜻이 겹쳐 보이고, agent-os의 이름과 달라집니다. 바뀌는 파일은 첫째 선택지와 같습니다.
   - 셋째 선택지 "지금 이름 그대로". 설명: '문턱'으로 둡니다. 바뀌는 파일이 없습니다. 걸리는 점: '문턱'이 컨텍스트 문턱, 검사 문턱과 섞여 쓰이고 agent-os와 이름이 달라집니다.

### 답을 읽은 방식

- 세 질문 모두 사용자가 추천(첫째 선택지)을 골랐다. 사용자는 선택지의 걸리는 점을 따로 고치라고 하지 않았다.
- "다시 올라온 항목"의 설명이 적은 걸리는 점(동작 표현 '잇는다'가 남는다)은 그대로 두었다. 그 동작 표현은 이번에 바꾸지 않는다고 설명에 적었다. 그래서 `.scratch/retro-queue/README.md`의 "만료된 항목을 새 항목이 이을 때"와 retro 스킬의 "잇는다"는 그대로다.
- "추가 기준 횟수"의 설명대로 줄여 쓴 "문턱"도 바꾸되 다른 뜻의 "문턱"은 두었다(아래 "바꾸지 않고 남긴 것"). 조사가 붙는 자리는 문장에 넣어 읽고 "추가 기준 횟수에 이르면", "추가 기준 횟수를 보지 않고 반영한다"로 적었다. 설명의 예문 "닿으면"과 "지나기 전에는"은 이 저장소의 지침 문장("다섯 번째이거나 손상이 한 번 났을 때 반영한다")에 맞춰 "이르면"으로 썼다.

## 앞 PR이 넘긴 것

- 앞 PR(66) claude-review 둘째 회차의 Nit: 용어집 배포 파일 묶음의 피할 말 "릴리스 자산"을 "GitHub 릴리스 자산"으로 맞출지. 맞췄다. 릴리스가 제품 한 벌의 이름이 되었고 GitHub에 올리는 게시물은 늘 "GitHub 릴리스"로 앞말을 붙이므로, 그 게시물에 딸린 파일을 부르는 피할 말도 같은 앞말을 붙여야 앞뒤가 맞는다. 풀이는 그대로다.
- 같은 회차에서 사용자가 고른 것: 출시 후보의 피할 말에 더한 "릴리스 후보"를 그대로 둔다. 지시문이 적은 대로 답은 "그대로 둔다 (Recommended)"였다. 이 답은 PR 66 코멘트에만 있고 이 세션은 그 코멘트를 읽지 않았으며, 위 지시문의 "이어받을 상태" 줄을 근거로 적는다. 용어집의 출시 후보 항목은 바뀌지 않았다.

## 한 것

### 이름 바꾸기

옛 이름이 쓰인 살아 있는 글을 줄마다 읽고 바꾸었다. 한꺼번에 치환하지 않았다. "문턱"이 다른 뜻으로도 많이 쓰이기 때문이다.

| 파일 | 바꾼 것 |
|---|---|
| `.claude/skills/retro/SKILL.md` | 머리 주석의 "더하는 것의 문턱", "닫힌 행을 이은 열린 행의 우선"(다시 올라온 열린 행). 4단계의 "새 훅·검사가 문턱을 지나면", "위 문턱을 지나고", 5단계의 "4단계의 문턱대로", 끝이 열린 결함 종류 항목, 이은 항목 둘, 만료 문단의 "그 항목을 이은 항목". 머리 주석이 코드 스팬 없이 든 agent-os의 옛 일지 번호 셋(`2026-09-22-10`, `2026-10-12-41`, `2026-10-17-07`)은 `sibling_overlap.py`가 걸려 코드 스팬에 넣었다 |
| `tools/queue_open_rows.py` | 독스트링의 "이은 항목이 5회차를 적으면" |
| `tests/tools/test_queue_open_rows.py` | 시험 `test_회차_5_이상인_항목은_반영할_때까지_만료하지_않는다`의 독스트링에서 "문턱을 넘은 항목", "문턱이 3에서 5로 올랐으니"(더하는 문턱의 뜻이다). 처음 훑을 때 정규식이 이 꼴을 잡지 못해 놓쳤고, 표준 축 셀프 리뷰가 잡았다. 시험 이름과 단언은 그대로다 |
| `tools/run_checks.py` | 독스트링의 옛 문장 `교정 루프(CLAUDE.md)의 문턱 전이다`. 줄이 넘쳐 `tools/rewrap_comments.py`로 감았다 |
| 열린 대기열 항목 여덟 | 승인 줄과 본문의 "끝이 열린 결함 종류"(`load-readtimeout-flake`, `load-sensitive-time-tests`, `load-time-assertion-margins`), "고침이라 문턱 없이 반영한다"(`check-quotes-untracked-scope`, `index-hangs-without-embedding-tei`, `serve-startup-test-load-margin`, `load-readtimeout-flake`), "반영할 문턱에 닿았다"(`measured-claim-beyond-probe`), "문턱을 채워"(`key-visible-in-user-terminal`) |
| `.scratch/retro-queue/glossary-plain-names-left.md` | 이름을 바꾸는 일의 진행을 적는 문단에 이 티켓이 끝낸 세 이름을 적었다 |
| `GLOSSARY.md` | 배포 파일 묶음의 피할 말 "릴리스 자산"을 "GitHub 릴리스 자산"으로 |

바꾼 열린 대기열 항목은 승인 줄을 건드린다. retro 4단계는 스스로 승인하는 기준을 옮겨 적거나 가리키는 모든 자리(대기열 폴더의 README와 항목 포함)를 바꾸는 것을 사람에게 넘기라고 하지만, 이번에는 기준(다섯 번째이거나 손상이 한 번 났을 때)과 회차는 그대로고 이름만 바뀌었고 사용자가 이름을 골라 바꾸라고 지시했으므로 넘기지 않았다. 닫힌 항목 둘(`gate-pipe-read-status`, `token-expiry-test-load-margin`)은 기록이라 고치지 않았다.

조사는 새 이름의 받침에 맞췄다. 새 이름의 끝 글자는 결함(받침 있음), 항목(받침 있음), 횟수(받침 없음)다. 옛 이름은 종류(받침 없음), 항목(받침 있음), 문턱(받침 있음)이다. 그래서 바꿀 조사가 둘 있었다. "종류라"가 "결함이라"가 되어야 했고(`load-readtimeout-flake`, `load-sensitive-time-tests`), "문턱을"이 "횟수를"이 되어야 했다("고침이라 추가 기준 횟수를 보지 않고", "추가 기준 횟수를 채워", "추가 기준 횟수에 이르고"로 문장째 풀었다). 첫 판에서는 이 일지가 "조사를 바꿀 곳은 없었다"고 적었고, "결함라" 둘이 남았다. 정규식 `(은|이|을|과|으로)`에 "라"가 없었고, 옛 이름의 끝 글자를 받침 있음으로 잘못 적어 둔 탓이다. 표준 축 셀프 리뷰와 명세 축 셀프 리뷰가 둘 다 잡았다(아래 "셀프 리뷰"). 고친 뒤에 받침에 맞지 않는 조사를 두 갈래 정규식으로 다시 훑었다. 받침 있는 낱말 뒤에 받침 없는 꼴이 온 것 `결함(라|가|는|를|와|로|나|면)`, `항목(는|가|를|와|로|라)\b`, 받침 없는 낱말 뒤에 받침 있는 꼴이 온 것 `횟수(은|이|을|과|으로|이라)`를 `.claude/skills/retro/SKILL.md`, `GLOSSARY.md`, `.scratch/retro-queue/*.md`, `tools/queue_open_rows.py`, `tools/run_checks.py`, `tests/tools/test_queue_open_rows.py`에서 찾았고 일치가 없었다.

### 선택 화면에 보인 수와 실제로 바뀐 수

| 이름 | 화면에 보인 수 | 실제로 바꾼 파일 |
|---|---|---|
| 끝이 열린 결함 종류 | 살아 있는 파일 4(retro 스킬 1, 열린 항목 3) | 4. 같다 |
| 이은 항목 | retro 스킬 1개 파일 2곳 | 2개 파일 5곳. retro 스킬의 "이은 항목" 셋(찾기 문단 52행 둘, 만료 문단 59행 하나)과 머리 주석의 "닫힌 행을 이은 열린 행" 하나, `tools/queue_open_rows.py` 독스트링 하나다. 화면에 보인 수는 retro 스킬만 센 값이어서 머리 주석과 도구 독스트링이 빠졌다(독스트링에는 "이은 항목"이 글자 그대로 있었으므로 왜 빠졌는지는 확인하지 못했다). 화면의 "2곳"도 줄 수(두 줄)였다 |
| 더하는 문턱 | retro 4곳, 도구 주석 1곳, 열린 항목 약 6개 | retro 4곳(머리 주석 1, 4단계 둘, 5단계 1), 도구 주석 1곳, 열린 항목 6개(`check-quotes-untracked-scope`, `index-hangs-without-embedding-tei`, `serve-startup-test-load-margin`, `load-readtimeout-flake`, `measured-claim-beyond-probe`, `key-visible-in-user-terminal`), 시험 독스트링 1곳(`tests/tools/test_queue_open_rows.py`). 시험 독스트링 하나가 화면에 보이지 않았다 |

받은 지시문은 이은 항목을 2개 파일 4곳으로 어림했고, 이 저장소에서 다시 센 값은 2개 파일 5곳이다. 화면에 보인 값과 실제 값이 갈린 곳은 둘이다. 이은 항목은 화면의 retro 스킬 1개 파일 2곳이 실제로는 2개 파일 5곳이었고, 더하는 문턱은 화면에 없던 시험 독스트링 1곳이 더해졌다. 마무리 보고에도 알린다. 이름 바꾸기로 고친 파일을 합치면, 화면에 보인 수로는 열 개(retro 스킬 1, `tools/run_checks.py` 1, 열린 대기열 항목 8. `load-readtimeout-flake`가 두 이름에 걸려 겹친다)였고 실제로는 열두 개(retro 스킬 1, `tools/queue_open_rows.py`와 `tools/run_checks.py` 2, `tests/tools/test_queue_open_rows.py` 1, 열린 대기열 항목 8)다. 거기에 `GLOSSARY.md`와 `glossary-plain-names-left.md`를 더하면 수정 파일은 열넷이고, 새 파일은 티켓과 이 일지 둘이다.

## 바꾸지 않고 남긴 것

다른 뜻의 "문턱"은 그대로 둔다(받은 지시문 1-1). 저장소에서 "문턱"이 든 살아 있는 파일을 디렉터리별로 모두 찾아(`.claude/`, `tools/`, `tests/`, `src/`, `.scratch/`, `docs/adr/`, `docs/constitution/`, `docs/agents/`, 루트의 마크다운, `.github/`) 읽고 가른 것이다. 처음 센 목록은 일부만 이름을 댔고, 명세 축 셀프 리뷰가 그 점을 짚어 아래로 넓혔다.

- 컨텍스트와 훅이 알리는 크기의 문턱: `.claude/rules/tools.md` 80·81행("문턱 위", "문턱 아래"), `.claude/skills/next-session/SKILL.md` 10행과 `handoff.md` 5행(세션 컨텍스트가 문턱(20만 토큰)을 넘었다), `.claude/skills/tidy-checkouts/SKILL.md` 31행(큰 결과 알림 훅의 글자 수).
- 훅이 쓰는 글자 수와 한국어 비율의 문턱: `tools/hook_grep_omitted.py`, `tools/hook_midturn_korean.py`, `tools/hook_stop_korean.py`, `tests/tools/test_hook_midturn_korean.py`(`test_산문_규칙과_문턱은_Stop_훅과_같다`의 이름).
- agent-os의 저장소 크기에 맞춘 시험의 수치 문턱: `tests/tools/test_check_instructions.py`(파일 수), `tests/tools/test_hook_report.py`(훅 수), `tests/tools/test_rewrap_comments.py`(파일 수), `.scratch/kickoff.md` 92행.
- 리랭크 점수, 코사인 유사도, 표본 일치 수의 문턱: `src/rag_engine/app/eval_report.py`, `src/rag_engine/app/eval_score_distribution.py`, `tests/app/test_eval_score_distribution.py`, `tests/tools/test_search_eval_run.py`, `.scratch/search-eval/spec.md`, `.scratch/search-eval/issues/`의 05·13·14·18, `.scratch/search-eval/probes/`(`README.md`, `eval_full_run_mutations.toml`, `no-answer-scores/`, `tei-gpu/device_diff.py`), `docs/adr/0017-min-score-argument-requires-reranker.md`와 `docs/adr/0018-search-evaluation-in-app-and-baseline-gate.md`(ADR 본문은 기록이다).
- `.scratch/retro-queue/measured-claim-beyond-probe.md` 9행의 "준비 문턱 5": 옛 티켓 문장을 인용한 것이다.
- 일지의 "문턱"과 닫힌 대기열 항목 둘의 "문턱 없이"는 기록이다.
- 용어집에는 이 세 이름의 항목이 없어(앞 PR이 하네스의 말은 운영 문서와 스킬이 정의한다고 보았다) 항목을 더하지 않았다. 용어의 수와 차례는 그대로다.
- "회차를 잇는다", "새 항목이 이을 때" 같은 동작 표현은 이번에 바꾸지 않았다(위 "답을 읽은 방식").

## 옛 이름의 잔존

찾은 명령(Grep, 낱말 사이 공백과 줄바꿈 허용)과 결과다.

처음에는 정규식이 좁았다. 이 일지의 첫 판은 "30개 파일, 남은 것은 기록뿐"이라고 적었지만, `tests/tools/test_queue_open_rows.py`의 독스트링("문턱을 넘은 항목", "문턱이 3에서 5로")을 잡지 못했다. 정규식이 "문턱 없이", "문턱 전이"처럼 뒤에 오는 낱말을 정해 두었기 때문이다. 표준 축과 명세 축 셀프 리뷰가 둘 다 잡았다. 아래는 고친 뒤에 다시 센 값이다.

- `끝이\s*열린|이은\s*항목|더하는\s*문턱|문턱\s*(없이|전이|을\s*(지|채|넘)|이\s*\d|대로)|반영할\s*문턱|더하는\s*것의\s*문턱|닫힌\s*행을\s*이은`을 `*.{md,py,toml,yml,yaml,json,txt}`에서 찾았다. 33개 파일이 나왔다. 일지가 26개(이 일지 포함)이고 나머지 일곱이다. 일곱은 받은 지시문의 원문, 이 티켓, `glossary-plain-names-left.md`(이름을 바꾼 일을 적은 문단), 닫힌 대기열 항목 둘(`gate-pipe-read-status`, `token-expiry-test-load-margin`), 그리고 정규식을 "문턱을 넘" 꼴까지 넓히며 걸린 다른 뜻의 문턱 둘(`.claude/skills/next-session/SKILL.md`의 컨텍스트 20만 토큰, `.scratch/search-eval/spec.md`의 점수 문턱)이다. 앞의 다섯은 기록이거나 일부러 옛 이름을 적은 곳이고 뒤의 둘은 다른 뜻이다.
- 핵심 낱말 하나로 `이은|열린\s*결함|열린\s*종류`를 `.claude/`의 `*.md`에서 찾았다. 남은 것은 `.claude/skills/retro/SKILL.md`의 머리 주석 "닫힌 행을 이은 열린 행의 우선"이었고 고쳤다. 다시 찾으면 일치가 없다.
- `문턱`만으로 살아 있는 파일을 디렉터리별로 찾아 읽고, 더하는 문턱의 뜻으로 쓰인 곳이 남지 않았음을 확인했다(남은 것은 위 "바꾸지 않고 남긴 것"의 다른 뜻뿐이다).

## 검증

- `uv run ruff check .`은 `All checks passed!`, `uv run ruff format --check .`은 `731 files already formatted`다.
- `uv run lint-imports`는 계약 둘이 kept이고 broken이 0이며 종료 코드 0이다(파이프 없이 파일로 돌려 종료 코드를 봤다).
- `uv run pyright`는 오류 0이고 종료 코드 0이다.
- `uv run python tools/check_instructions.py`는 종료 코드 0이다.
- `uv run python tools/plan_table.py --check`와 `uv run python tools/check_adr_pointers.py`는 0으로 끝났다.
- `uv run python tools/sibling_overlap.py`는 처음에 1로 끝났다. 회고 스킬 머리 주석이 agent-os의 옛 일지 번호 셋을 코드 스팬 없이 적어서다(이 파일을 건드려 걸렸다). 코드 스팬에 넣고 다시 쳐 0으로 끝났다(번호 겹침 없음, 헌법 번호는 그대로 1.3.6).
- `uv run pytest tests/tools/test_queue_open_rows.py tests/tools/test_check_instructions.py tests/tools/test_rewrap_comments.py -q`는 `267 passed`다. 전체 `uv run pytest`는 손으로 치지 않았다. 이 PR은 마크다운과 파이썬 주석·독스트링만 바꾸고(코드 동작을 바꾸지 않았다), 커밋에서 pre-commit의 검사 러너가 전체 pytest를 돈다. 그 결과는 아래 "PR 직전 리뷰" 절에 적는다.
- 셀프 리뷰를 반영한 뒤에 `uv run ruff check .`(All checks passed!), `uv run ruff format --check .`(732 files already formatted), `uv run pyright`(0 errors), `uv run lint-imports`(2 kept, 0 broken), `uv run python tools/check_instructions.py`(출력 없이 종료 코드 0), `uv run pytest tests/tools/test_queue_open_rows.py tests/tools/test_check_instructions.py tests/tools/test_rewrap_comments.py -q`(267 passed)를 다시 쳤다. `uv run python tools/sibling_overlap.py`는 번호 겹침이 없다고 답했고, 형제 워크트리 `release-image-spec`이 커밋하지 않은 채 `.scratch/retro-queue/measured-claim-beyond-probe.md`를 고치는 중이라고 알렸다(나중에 병합하는 쪽의 글자 충돌 후보다. 이 PR이 고친 줄은 "다섯 번째라 반영할 문턱에 닿았다" 한 줄이다).

## 셀프 리뷰

`code-review` 스킬로 돌렸다. 범위는 base `bc31442`(`origin/dev`), 수정 파일 13개, 미추적 파일 둘(티켓과 이 일지), 커밋 0개였다. 표준 축은 Sonnet 5.5 / high 서브에이전트, 명세 축은 이 세션의 모델을 이은 서브에이전트가 돌았다. 이 변경은 이름만 바꾸고 단계를 바꾸지 않아 갈래 밟기 문단은 브리프에 넣지 않았다. 코드의 동작을 바꾸지 않아 상태 전이 갈래(d)도 넣지 않았다. 보고는 받은 턴에 아래로 옮겼다.

### 표준 축

| 지적 | 판정 | 반영 |
|---|---|---|
| Major. `load-readtimeout-flake.md`와 `load-sensitive-time-tests.md`에 "결함라"가 남았다. 새 이름 "결함"은 받침이 있어 "결함이라"여야 한다. 일지의 "조사를 바꿀 곳은 없었다"와 티켓의 셋째 수용 기준이 거짓이 된다 | 맞다. `git grep`으로 두 곳을 봤다 | "결함이라"로 고쳤다. 일지의 조사 문단을 다시 썼고(옛 이름 "종류"는 받침이 없다. 훑는 정규식에 "라"를 더하고 받침 없는 낱말 뒤의 받침 있는 꼴도 훑는다) 다시 훑어 일치가 없다 |
| Major. `tests/tools/test_queue_open_rows.py` 305·306행의 시험 독스트링에 더하는 문턱의 뜻인 "문턱을 넘은 항목", "문턱이 3에서 5로"가 남았다. 일지의 "남은 옛 이름은 기록뿐"이 거짓이다 | 맞다. 그 정규식이 이 꼴을 잡지 못했다 | "추가 기준 횟수에 이른 항목", "추가 기준 횟수가 3에서 5로"로 고쳤다. 시험 이름과 단언은 두었다. 일지의 잔존 절을 정규식을 넓혀 다시 썼고 "바꾸지 않고 남긴 것"에 이 줄을 더하지 않았다(바꿨으므로) |
| Minor. `retro/SKILL.md` 52행 "그 항목을 `…k회차`로 다시 올라온 항목을"이 비문이다("올라온"은 자동사다) | 맞다 | "그 항목에서 `…k회차`로 다시 올라온 항목을"로 고쳤다 |
| Minor. 일지의 닫힌 주장 둘("일치가 없다", 다른 뜻의 문턱 목록)이 부정확하다. 목록에 `tests/tools/`의 문턱 넷이 없다 | 맞다 | "바꾸지 않고 남긴 것"을 디렉터리별로 모두 찾아 읽고 가른 목록으로 넓혔다. 명세 축의 같은 지적과 함께 반영했다 |
| Nit. 머리 주석의 일지 번호 셋을 코드 스팬으로 감싼 것은 이 이름 바꾸기와 무관하다 | 남겼다 | `sibling_overlap.py`가 이 파일을 건드린 변경에서 1로 끝나 막았다. 일지의 "한 것"에 까닭을 적었다 |
| Nit. 새 이름 "추가 기준 횟수"의 정의가 retro 4단계에 없다 | 남겼다 | 옛 이름 "문턱"도 같았고, 정의는 CLAUDE.md 교정 루프가 이미 적고 있다(같은 실수의 다섯 번째이거나 손상이 한 번 났을 때 더한다). 새 정의를 더하면 지침을 더하는 일이라 이 PR의 범위 밖이다 |

### 명세 축

| 지적 | 판정 | 반영 |
|---|---|---|
| (c) 결함라 둘. 셋째 수용 기준이 깨졌다 | 표준 축 첫 지적과 같다 | 위와 같다 |
| (c) 더하는 문턱의 뜻으로 쓴 "문턱"이 시험 독스트링에 남았다 | 표준 축 둘째 지적과 같다 | 위와 같다 |
| (c) 둘째 수용 기준의 "한 줄씩"을 일지 목록이 지키지 않는다 | 맞다 | 위와 같다 |
| (c) 일지의 "30개 파일 중 일지 스물셋"이 재현되지 않는다 | 맞다. 정규식을 넓히고 다시 센 값은 33개 파일(일지 26, 나머지 7)이다 | 일지의 잔존 절을 다시 썼다 |
| (a) 일곱째 수용 기준의 "테스트"에 전체 `uv run pytest`를 안 돌렸다 | 맞다. 이 PR은 파이썬 주석·독스트링만 바꾸고 전체 pytest는 커밋의 검사 러너가 돈다 | 티켓의 일곱째 수용 기준을 검사 넷과 고친 파일에 닿는 시험은 초록이고 전체 pytest는 커밋의 검사 러너가 돌아 초록이라는 문장으로 고쳤다. 커밋 결과는 "PR 직전 리뷰" 절에 적는다 |
| (a) 여섯째 수용 기준의 "스킬 점검"을 일지에서 찾을 수 없다 | 맞다. 저장소에 "스킬 점검"이라는 절차가 없다(`스킬 점검`을 Grep으로 찾아 일치가 없었다). 티켓 문구가 틀렸다 | 티켓을 "지침 검사 `tools/check_instructions.py`와 그 시험, 형제 겹침 `tools/sibling_overlap.py`"로 고쳤다. 둘 다 위에서 돌렸다 |
| (a) 일지의 선택 화면 글에 괄호 둘("받은 지시문은 2개 파일 4곳으로 어림했고…", "항목 수는 어림이고…")이 있는데 지시문이 인용한 답에는 없다 | 남겼다 | 그 괄호는 화면에 올린 글에 실제로 있었다(이 세션이 올린 글이다). 지시문이 인용한 것은 사용자의 답의 라벨뿐이다 |
| (a) 일지가 가리키는 "PR 직전 리뷰" 절이 아직 없다 | 맞다 | PR 직전 리뷰를 돌린 뒤에 쓴다 |
| (b) 범위 넘침 없음 | | |

### 고친 것, 남긴 것, 다시 돌린 명령

- 고친 것: 위 표의 맞다 판정 전부(조사 둘, 시험 독스트링 하나, 52행 비문 하나, 일지의 조사 문단과 잔존 절과 남긴 목록과 파일 수 셈, 티켓의 수용 기준 둘). 일지에 새로 쓴 사실 문장은 "33개 파일(일지 26, 나머지 7)", 수정 파일 열넷과 이름 바꾸기로 고친 파일 열둘(화면에 보인 수로는 열 개), `스킬 점검`을 Grep으로 찾아 일치가 없었다는 것, 다른 뜻의 문턱 목록은 디렉터리별로 모두 찾아 읽고 가른 것이라는 것이다. 이 넷은 PR 직전 리뷰에 밀 주장으로 넘긴다.
- 남긴 것: 위 표의 Nit 둘과 괄호 둘의 판정.
- 다시 돌린 명령: 위 "검증"의 마지막 두 줄. 전체 pytest는 커밋이 부르는 pre-commit의 검사 러너가 돈다.

## 커밋

커밋 `f01c704`(제목 69자)는 pre-commit을 모두 지났다. 첫 시도는 제목이 73자라 commit-msg 검사(한도 72자)에서 막혔고, 그 시도에서도 전체 pytest는 초록이었다(391.8초). 제목을 줄인 둘째 시도에서 검사 러너는 열 검사가 모두 Passed였고 pytest는 434.9초에 초록이었다. 인용 대조는 첫 시도에서 경고 8건(티켓 1건, 일지 7건)을 냈다. 일지와 티켓이 따옴표로 감싼 문장 가운데 저장소에 글자 그대로 없는 것이었고, 따옴표를 떼거나 코드 스팬으로 바꿔 둘째 시도에서 경고 0건이 되었다. 앞서 "검증"과 "셀프 리뷰"가 미룬 전체 pytest의 결과가 이것이다.

## PR 직전 리뷰

### CodeRabbit CLI

`coderabbit-review` 에이전트가 CLI(0.7.5)를 `--base origin/dev`로 돌렸다. `review_completed`로 끝났고 좌석은 `Plan: Free`, `Seat: not assigned`였다. Critical과 Major는 없었고 지적은 둘이었다. 일지에 쓴 사실 문장을 겨냥해 달라고 넘긴 주장 다섯도 재 보았다.

| 지적 | 판정 | 반영 |
|---|---|---|
| Minor. 일지 "이은 항목" 행의 까닭("글자만 센 값이어서 도구 독스트링을 놓쳤다")이 앞뒤가 안 맞는다. 바뀌기 전 `tools/queue_open_rows.py` 독스트링에 그 글자가 있었다 | 맞다. `git show`로 독스트링 줄이 바뀐 것을 봤다 | 까닭을 "retro 스킬만 센 값이어서 빠졌다. 왜 빠졌는지는 확인하지 못했다"로 고쳤다. 센 수(2개 파일 5곳)는 그대로다 |
| Minor. 일지가 가리키는 "PR 직전 리뷰" 절이 없고, `267 passed`는 시험 세 파일의 결과다 | 부분만 맞다. 그 문장이 전체 pytest가 아니라고 이미 밝혔다 | 이 절과 위 "커밋" 절을 더했다. 전체 pytest의 결과는 "커밋" 절에 있다 |

주장별 확인은 다섯 모두 사실이었다.

- 옛 이름 잔존: 넓힌 정규식을 그대로 돌려 33개 파일(일지 26, 나머지 7)이 나왔다. 나머지 7은 지시문 원문, 이 티켓, `glossary-plain-names-left.md`, 닫힌 항목 둘, 다른 뜻의 "문턱"이 든 `next-session/SKILL.md`와 `search-eval/spec.md`다. 열린 항목 `glossary-plain-names-left.md`는 이름을 바꾼 일을 옛 이름과 새 이름을 짝지어 적은 문단이라 일부러 남겼다.
- 조사: 대상 파일을 어긋난 조사 정규식으로 훑어 일치가 0건이었고 diff를 읽어도 없었다.
- 다른 뜻의 문턱: `src/`, 훅, `tests/app/`, `.scratch/search-eval/`, ADR의 것은 그대로다. 에이전트는 `tests/tools/test_hook_report.py`가 목록에서 빠졌다고 적었지만, 목록은 "agent-os의 저장소 크기에 맞춘 시험의 수치 문턱" 줄에 그 파일을 이미 들고 있다(오탐).
- 수: 수정 14개, 새 파일 2개, 이름 바꾸기로 고친 파일 12개가 맞다.
- 수용 기준 7개: 모두 사실이다(검사 넷과 시험의 초록은 일지 기록에 기댔고, 전체 pytest는 위 "커밋"의 결과다).

Nit 셋은 남겼다. 머리 주석의 일지 번호 코드 스팬은 위에서 까닭을 적었다. "회차를 잇는다"는 동사를 일부러 두었다고 이미 적었다. `tools/run_checks.py` 독스트링의 줄바꿈이 어색한 것은 `tools/rewrap_comments.py`가 감은 결과다.

### 보안 리뷰

내장 `/security-review`를 돌렸다. 바뀐 것이 마크다운과 독스트링·주석뿐이라 실행 코드의 변경이 없고, 확신도 8 이상의 발견은 없었다.

### 고친 것, 남긴 것

- 고친 것: 일지 "이은 항목" 행의 까닭 한 문장, 이 절과 "커밋" 절의 추가. 새로 쓴 사실 문장은 위 "커밋"의 숫자(제목 69자, 391.8초, 434.9초, 경고 8건)이고 출력 파일을 열어 옮겼다.
- 남긴 것: Nit 셋, 오탐 한 건(`test_hook_report.py`).
- 다시 돌린 명령: 일지만 고쳤고 이 고침은 다음 커밋의 pre-commit이 돈다.

## 회고

`retro` 스킬을 돌렸다. 1차 자료는 이 일지와 이 세션이다. 후보는 셋이었고 승인 둘, 기각 하나, 넘김 0건이었다. 사용자에게 묻지 않았다.

| 후보 | 판정 | 근거가 된 조건 |
|---|---|---|
| 커밋 제목이 73자(한도 72자)라 `parallel-checks`를 약 6.5분 돈 뒤에야 `commit-msg`가 막았다. 막힌 뒤 제목을 줄이지 않고 같은 제목으로 다시 커밋을 띄워 중간에 멈췄다 | 승인. 기존 항목 `commit-msg-after-slow-checks`의 5회차 | 사건: 위의 6.5분과 재시도. 층: 이미 있는 처방(`git commit -m`의 제목을 앞서 보는 PreToolUse 훅)이 가장 강한 층이다. 되돌림: 훅 하나를 넣는 PR이다 |
| 이름을 바꾸는 PR이 옛 이름의 꼴을 손으로 짠 정규식으로 훑어 놓친 꼴(시험 독스트링의 문턱, "결함라" 둘)을 셀프 리뷰가 잡았고, 선택 화면에 올린 수(10개 파일)도 실제(12개)와 어긋났다 | 승인. 새 항목 `rename-sweep-misses-forms`의 1회차 | 사건: 위의 놓친 꼴과 수의 어긋남. 층: 지침이 아니라 훑기 도구(자동 검사)로 승인한다. 되돌림: 도구 하나를 넣는 PR이다 |
| 인용 대조가 일지와 티켓의 따옴표 인용 8건을 경고했다 | 기각 | 검사가 그 자리에서 알렸고 따옴표를 떼어 해결했다 |

승인한 둘은 모두 더하는 것이라 이 세션에서 반영하지 않았다. 첫째 항목은 이번으로 5회차가 되어 `next-session` 결정표의 chore 배치 조건에 든다. 둘째 항목은 1회차라 대기열에 두었다.

- 만료: `uv run python tools/queue_open_rows.py`를 작업 트리와 `--ref origin/dev`로 모두 돌렸고 만료할 항목은 둘 다 없었다.
- 일지에만 남기는 것: 서브에이전트(CodeRabbit 보고)가 `tests/tools/test_hook_report.py`가 목록에서 빠졌다고 적은 것은 오탐이었다. 목록은 그 파일을 이미 들고 있었다.

## 다음

이 PR을 병합한 뒤에는 받은 지시문 5-2의 차례 2, "주체 → 요청자" 이름 바꾸기 PR이 이어진다(`.scratch/glossary-names-input.md`). 그 전에 chore 배치 조건에 든 `commit-msg-after-slow-checks`(5회차)를 반영할지 `next-session`의 결정표가 정한다. 주 체크아웃이 `origin/dev`보다 뒤처져 있어 새 세션은 시작 전에 `tidy-checkouts`로 당겨야 하고, 그것을 막는 추적하지 않는 파일 둘은 사람이 정리해야 한다.
