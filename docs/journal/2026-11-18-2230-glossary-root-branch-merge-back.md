# glossary-root-branch-merge-back: "루트 브랜치"와 "되돌려 합치기"를 agent-os의 결정에 맞춰 바꾼다 · 2026-11-18

앞 세션(일지 `2026-11-18-1939-glossary-principal-to-requester.md`)이 PR 69를 병합하고 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-root-branch-merge-back.md`, 브랜치는 `chore/glossary-root-branch-merge-back`이고, 새 워크트리 `glossary-root-branch-merge-back`에서 `origin/dev`(d0bf91b)로 브랜치를 따서 했다. 용어집의 이름을 agent-os의 결정에 맞추는 일(받은 지시문의 원문 `.scratch/glossary-names-input.md`. 아래에서 "받은 지시문"은 이 글이다)의 넷째 PR이고, 받은 지시문 5-2의 차례 3이다. 계기, 세션을 열며 한 정리, 도구가 글자를 찾는지 본 것, 물은 것과 사용자의 답, 한 것, 바꾸지 않고 남긴 것, 옛 이름의 잔존, 검증을 차례로 두고, 그 뒤의 리뷰와 회고는 한 차례씩 덧붙인다.

## 계기

사용자가 아래 지시문을 첫 메시지로 넣어 이 세션을 열었다. 지시문의 핵심 줄이다.

```
"루트 브랜치"와 "되돌려 합치기"를 새 이름으로 바꾸는 PR(받은 지시문 5-2의 차례 3)을 티켓 .scratch/harness/issues/glossary-root-branch-merge-back.md로 쓰고 한다

다음 작업: … "루트 브랜치"를 "주 체크아웃이 따르는 브랜치"로, "되돌려 합치기"를 "운영에서 개발로 합치기"로 바꾸고 살아 있는 글의 같은 말을 맞춘다(그 파일 1-1절). "되돌려 합치기"는 PR의 종류를 가리키는 말로 스킬과 도구가 쓰므로, 도구가 그 글자를 찾거나 찍는지 먼저 보고, 그렇다면 도구와 시험을 한 PR에서 함께 고친다.
브랜치: chore/glossary-root-branch-merge-back
이어받을 상태: … 헌법이나 PRD 본문에 이 낱말이 있으면 바꿀지를 선택 화면으로 묻고, 바꾸면 헌법 버전 규칙을 따른다. 코드 식별자, ADR 결정 제목, 일지는 바꾸지 않는다. 대기열 rename-sweep-misses-forms를 훑기에 참고하고 커밋 제목은 72자 안에 둔다
이번 요청 범위: PR과 병합까지
```

이 일은 retro가 승인한 대기열 항목이 아니라 사용자의 직접 지시다. 티켓의 대기열 줄에는 `glossary-plain-names-left`(이름을 바꾸는 일 전체)와, 지시문이 참고하라고 한 `rename-sweep-misses-forms`를 적었다.

## 세션을 열며 한 정리

지시문대로 이 세션의 제목을 브랜치 이름으로 바꾸고(`set_session_title`) `tidy-checkouts` 스킬을 먼저 돌렸다. 이 세션은 주 체크아웃(`C:\project\rag-engine`)에서 열렸고 `git fetch origin`을 쳤다.

- 주 체크아웃은 당기지 못했다. 루트는 dev이고 `HEAD`는 6957194, `origin/dev`는 d0bf91b이며, 원격에 없는 로컬 커밋은 0개다. `git status --porcelain`에 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 나와 깨끗하지 않았다. 스킬의 "주 체크아웃이 따르는 브랜치 위에 있는데 깨끗하지 않다" 갈래라 건드리지 않았고, 지시문의 "확인할 선행 조건"이 이미 알린 파일이다.
- 지운 것은 워크트리와 브랜치 `docs/release-image-spec` 하나다. 그 세션 `local_47a0459a…`이 쉬는 세션(마지막 활동 11:43)이라 `judge`가 `끝낸다`를 냈고, 직전에 `list_sessions`를 다시 읽어 실행 중이 아님을 보고 `end-holders`로 그 세션의 프로세스(claude.exe, cmd.exe)를 끈 뒤 `judge`를 다시 쳐서 나온 `지운다`를 `remove`로 쳤다.
- 남긴 워크트리와 이유는 다음과 같다. `05-full-run-rerank`는 그 폴더를 작업 디렉터리로 쥔 프로세스(tail.exe, grep.exe, cut.exe)가 있다. `10-public-docs-questions`는 바뀐 파일이 있다. `13-first-judge-run`은 세션 `local_a6780d9a-3397-4c26-babc-619f7a2ab4e6`의 python.exe 열둘이 쥐고 있다. `16-search-latency-probe-f30c20`과 `relaxed-grothendieck-e892b9`는 앱의 표지가 있어 앱의 정리에 맡긴다. `glossary-harness-small-names`와 `glossary-release-names`와 `release-image`는 그 폴더를 쥔 프로세스가 있다. `glossary-principal-to-requester`는 그 브랜치가 제목인 세션이 돈다. `release-image-tickets`와 `release-search-eval`은 병합된 PR이 없다.
- 사람에게 넘긴 것은 워크트리 `14-reindex-version-switch` 하나다. 병합된 PR의 머리와 브랜치 끝이 다르다. 앞 세션들도 같은 것을 넘겼고, 지시문대로 보고만 하고 답을 기다리지 않았다.
- 휴지통은 비우지 못했다. `empty-trash`를 쳤고 `.venv` 폴더 여덟이 남았다(앞 세션의 일곱에 `release-image-spec`의 것 하나가 더해졌다). 모두 `.pyd` 파일 하나에서 접근이 거부됐다(WinError 5). 다음 정리가 다시 본다.

그 뒤 `EnterWorktree`(name `glossary-root-branch-merge-back`)로 새 워크트리에 들어갔고, 앱이 붙인 브랜치 `worktree-glossary-root-branch-merge-back`에서 `git switch -c chore/glossary-root-branch-merge-back origin/dev --no-track`으로 브랜치를 바꿨다(시작 커밋이 이미 d0bf91b, `origin/dev`였다).

## 도구가 글자를 찾거나 찍는지 본 것

지시문은 "되돌려 합치기"가 PR의 종류를 가리키는 말로 스킬과 도구에 쓰이므로 도구가 그 글자를 찾거나 찍는지 먼저 보라고 했다. `git grep -n -P "루트\s*브랜치|되돌려\s*합"`을 `tools`, `tests`, `src`, `.github`에 쳐서 읽었다(코드를 읽은 것이다).

- 도구와 시험의 코드는 두 이름을 문자열로 찾거나 찍지 않는다. 일치는 주석 셋(`tools/check_ticket.py`, `tools/hook_git_main_commit.py`의 독스트링, `tests/tools/test_check_ticket.py`)과 독스트링 하나(`tests/tools/test_hook_git_main_commit.py`)와 훅 설명문 하나(`tools/hook_payloads.toml`의 `note`)뿐이다. `note`는 `tools/run_hooks.py`가 실행 결과 줄과 오류 문구에 덧붙여 찍을 뿐이고, `tests/tools/test_run_hooks.py`는 실패한 사례의 `note`를 목록에 모아 그 목록이 비었는지만 본다(두 파일에서 `\bnote\b`를 찾아 읽었다). 글자를 맞대는 시험은 없다. 그래서 도구와 시험의 코드는 고치지 않고 글만 맞췄다.
- 시험이 맞대는 문구 `주 체크아웃 미갱신: 루트는 <브랜치>`(`tests/tools/test_hook_prompt_directive.py`)의 "루트"는 주 체크아웃을 줄여 부른 말이지 "루트 브랜치"가 아니다. 그래서 스킬과 도구가 쓰는 "루트"(주 체크아웃) 단독 표현은 바꾸지 않았다.
- 스킬이 절 이름을 글자 그대로 가리키는 곳이 있다. `next-session`의 `merge.md`에 `## 되돌려 합치기` 절이 있고, 결정표(`SKILL.md`)의 계기 이름, 헌법 `operations.md`가 `merge.md`("병합 방법", "되돌려 합치기")를 가리키는 문장이 그 절 이름을 든다. 절 이름을 바꾸면 이 가리킴을 함께 바꿔야 해서 한 PR에서 함께 고쳤다. `tools/check_instructions.py`가 이 가리킴을 판정하는지는 고친 뒤 돌려서 초록임을 봤다.

## 물은 것과 사용자의 답

받은 지시문 1절은 이 이름을 사용자에게 다시 묻지 않고 한다고 적었다. 새 이름은 사용자가 agent-os에서 이미 골랐으므로 묻지 않았다. 그러나 이 세션의 지시문이 헌법이나 PRD 본문에 이 낱말이 있으면 선택 화면으로 묻고 바꾸라고 적었다. 화면을 올리기 전에 한 일은 옛 이름이 쓰인 곳을 `git grep`으로 세어 문맥을 읽은 것이다. 헌법 `principles.md`, `tech.md`, `docs/PRD.md`에는 두 이름이 없고, 헌법 `operations.md`에 "되돌려 합…" 꼴이 11곳("되돌려 합치기" 9곳과 "되돌려 합치는", "되돌려 합친다" 둘), "루트 브랜치"가 2곳(`grep -o`로 센 수), 합쳐 13곳 있다. 헌법 판정 도구(`tools/check_constitution_version.py`의 독스트링)는 `operations.md`의 변경이면 어느 것이든 버전 줄을 올리라고 한다.

질문은 하나였고 선택지는 셋이었다. 아래의 질문, 선택지, 설명은 이 세션에서 올린 글자 그대로이고, `> 사용자:` 줄이 답이다.

1. 질문(머리 `헌법 문구`)

   ```
   헌법 운영 문서(docs/constitution/operations.md)에 쓰인 "루트 브랜치"와 "되돌려 합치기"(합쳐 13곳)도 새 이름으로 바꿀까요? 앞의 말은 "주 체크아웃이 따르는 브랜치", 뒤의 말은 "운영에서 개발로 합치기"로 바뀝니다.
   ```

   > 사용자: "바꾼다, 헌법 버전 1.3.8 (Recommended)"

   - 첫째 선택지 `바꾼다, 헌법 버전 1.3.8 (Recommended)`. 설명:

     ```
     운영 문서의 두 이름을 스킬·도구와 똑같이 바꿉니다. 뜻은 그대로이고 글자만 바뀌므로 헌법 버전은 문구 수정(patch)으로 1.3.7에서 1.3.8로 올립니다. 바뀌는 헌법 파일은 operations.md와 헌법 README.md의 버전 줄 둘이고, 바꾼 까닭은 ADR 0016의 이력에 한 항목으로 남깁니다. 걸리는 점: 열려 있는 형제 브랜치가 같은 버전을 쓰면 번호를 비켜 가야 합니다(지금 형제 겹침 검사는 겹침이 없다고 합니다).
     ```

   - 둘째 선택지 `헌법은 그대로 두고 나머지만 바꾼다`. 설명:

     ```
     스킬, 도구 설명문, 워크플로 주석, 진행 중인 명세는 바꾸고 operations.md는 옛 이름으로 둡니다. 헌법 버전은 1.3.7 그대로입니다. 걸리는 점: operations.md가 스킬의 절 이름을 글자 그대로 "되돌려 합치기"라고 가리키는 문장이 두 곳 있어, 스킬의 절 이름이 바뀌면 그 문장이 없는 절을 가리키게 됩니다. 이를 피하려면 그 문장만 따로 고쳐야 하는데 그것도 헌법 문구라 결국 버전을 올리게 됩니다.
     ```

   - 셋째 선택지 `지금은 정하지 않는다`. 설명:

     ```
     헌법과 스킬의 절 이름을 모두 옛 이름으로 두고, 도구 설명문과 워크플로 주석 같은 헌법 밖의 글만 바꿉니다. 스킬과 헌법의 이름이 어긋나지 않게 하려면 스킬의 절 이름도 건드리지 않아야 해서 이번 PR이 거의 비게 됩니다. 걸리는 점: 이름 바꾸기의 차례 3이 끝나지 않고 사용자에게 다시 묻는 일이 한 번 더 생깁니다.
     ```

### 답을 읽은 방식

- 사용자가 추천(첫째 선택지)을 골랐다. 그래서 `operations.md`의 두 이름을 바꾸고 헌법 버전을 올렸다. 형제 겹침 검사(`tools/sibling_overlap.py`)는 형제가 쓴 가장 높은 헌법 버전을 1.3.7(`origin/dev`)이라 알렸고, 이 브랜치의 새 번호는 1.3.8이며 번호 겹침이 없다.
- 선택 화면이 적은 대로 바꾼 까닭은 ADR 0016의 이력에 한 항목으로 남겼다. 두 이름이 본문에 든 ADR은 0016(옛 이름이 든 줄 10줄)과 0020(1줄)이다(이 PR 전의 `git grep -c`로 찾았다). 0020에도 이력 항목을 달았다. 본문은 글자 그대로 두었다. ADR 규칙(`.claude/rules/adr.md`)대로 이력을 더하기 전에 `domain-modeling` 스킬을 불렀고, 이름만 바뀐 이력이라 본문 문장을 거짓으로 만들지 않아 `(바뀜: …)` 포인터는 달지 않았다. 이 저장소의 용어는 `GLOSSARY.md`가 아니라 운영 문서에 둔다는 ADR 0016 본문의 결정이 있어(`GLOSSARY.md`에는 두 이름의 항목이 없다), 용어집의 피할 말 줄 대신 `operations.md`의 용어 문단과 `tidy-checkouts`의 정의 문장에 옛 이름을 괄호로 적었다.

## 한 것

### 이름 바꾸기

옛 이름이 쓰인 살아 있는 글을 파일마다 문맥을 읽고 바꾸었다. 어미가 붙지 않은 명사 꼴("되돌려 합치기", "루트 브랜치")은 스크래치패드의 스크립트로 한 번에 바꾸고, 어미가 바뀐 꼴("되돌려 합친다", "되돌려 합치지", "되돌려 합칠", "되돌려 합치는")은 문장마다 정한 말로 바꾸는 둘째 스크립트로 횟수를 단언하며 바꿨다. "main을 dev에 되돌려 합친다"는 "main을 dev에 합친다"로 두었다(`main`과 `dev`가 문장에 있어 "되돌려"를 뺀 것이다. 기존 시험 `tests/tools/test_hook_git_main_commit.py`가 이미 쓰는 커밋 메시지 `chore: main 을 dev 에 합친다`와 같은 꼴이다). 읽어 보니 문장이 어색해진 곳 셋(`implement`의 "주 체크아웃이 따르는 브랜치인데", `directive.md`의 "주 체크아웃이 주 체크아웃이 따르는 브랜치", `open-session`의 "루트가 주 체크아웃이 따르는 브랜치")은 직접 고쳤고, 정의 문장 둘(`tidy-checkouts`와 `operations.md`)은 순환 정의("A는 A다")가 되어 풀어 썼다.

| 파일 | 바꾼 것 |
|---|---|
| `.claude/skills/next-session/merge.md` | 절 이름 `## 운영에서 개발로 합치기`와 그 절을 가리키는 곳, 병합 방법 표의 PR 종류 이름, 어미가 바뀐 꼴 |
| `.claude/skills/next-session/SKILL.md` | 결정표 두 줄의 계기 이름과 설명 |
| `.claude/skills/next-session/directive.md` | 워크트리 문장의 조건 |
| `.claude/skills/tidy-checkouts/SKILL.md` | 설명(frontmatter), 정의 문단, `<주 체크아웃이 따르는 브랜치>` 자리 표시 일곱 곳, 갈래 이름 |
| `.claude/skills/open-session/SKILL.md`, `.claude/skills/implement/SKILL.md` | 각 한 곳 |
| `docs/constitution/operations.md` | 용어 문단(정의와 옛 이름), 보호 브랜치·병합·리뷰 봇 절의 PR 종류 이름 |
| `docs/constitution/README.md` | 버전 줄 1.3.7 → 1.3.8 |
| `docs/agents/issue-tracker.md` | PR 종류 이름 한 곳 |
| `docs/adr/0016-…`, `docs/adr/0020-…` | 이력에 항목 하나씩. 본문은 그대로다 |
| `.github/workflows/claude-code-review.yml` | 주석 두 곳 |
| `.scratch/release-image/spec.md` | 진행 중인 기능의 명세 세 줄(사용자 이야기 50, 넘겨받음 줄, 정함 줄) |
| `tools/check_ticket.py`, `tools/hook_git_main_commit.py`, `tools/hook_payloads.toml`, `tests/tools/test_check_ticket.py`, `tests/tools/test_hook_git_main_commit.py` | 주석·독스트링·훅 설명문만. 코드는 그대로다 |

조사는 바꿀 곳이 없었다. "루트 브랜치"와 "주 체크아웃이 따르는 브랜치"는 끝 글자가 둘 다 "치"이고, "되돌려 합치기"와 "운영에서 개발로 합치기"는 둘 다 "기"여서 받침이 없다. 확인으로 `(주 체크아웃이 따르는 브랜치|운영에서 개발로 합치기)(은|을|과|이|으로)(?![가-힣])`를 추적 파일과 미추적 파일에서 찾았고 일치가 없었다.

### 선택 화면에 보인 수와 실제로 바뀐 수

| 이름 | 화면에 보인 수 | 실제로 바꾼 파일 |
|---|---|---|
| 헌법 | `operations.md` 13곳(둘째·셋째 선택지에 쓴 "두 곳"은 스킬이 가리키는 문장) | 헌법 파일은 `operations.md`와 README의 버전 줄 둘. 같다 |
| 받은 지시문의 어림 | 되돌려 합치기 13개 파일 73곳, 루트 브랜치 6개 파일 34곳(지시문 1-1) | 수정 18개 파일(`git diff --stat`, 72줄 추가·62줄 삭제). 지시문의 어림에는 기록(일지, 끝난 하네스 기능 `dev-branch`의 티켓, 받은 지시문의 원문)이 들어 있어 이 PR이 고치지 않았다. 새 파일은 티켓과 이 일지다 |

## 바꾸지 않고 남긴 것

- 기록: 일지 전부, 받은 지시문의 원문 `.scratch/glossary-names-input.md`, 끝난 하네스 기능 `dev-branch`의 티켓 다섯과 계획(`.scratch/dev-branch/`. 티켓 다섯이 모두 병합되었고 이 기능은 하네스 기능이라 끝 줄을 쓰지 않지만 살아 있는 명세가 아니라 병합된 변경의 기록으로 본다), `.scratch/release-image/probes/squash_title/run.py`의 독스트링(프로브라 손으로 고치지 않는다).
- ADR 본문: 0016과 0020의 옛 이름은 본문이라 두고 이력에 새 이름으로 읽으라고 적었다. ADR 결정 제목에는 두 이름이 없다.
- 단독으로 쓰인 "루트": 주 체크아웃을 줄여 부른 말(`주 체크아웃 미갱신: 루트는 <브랜치>`, "루트가 깨끗하다" 등)은 바꾸지 않았다. 이 문구는 시험(`test_hook_prompt_directive.py`)이 맞대고, 지시문 1-1은 "루트 브랜치"만 바꾸라고 했다.
- 옛 이름을 일부러 적은 곳: `docs/constitution/operations.md`의 용어 문단(두 이름), `.claude/skills/tidy-checkouts/SKILL.md`의 정의 문장, ADR 0016과 0020의 이력 항목, 이 티켓과 이 일지.
- 다른 뜻의 "되돌려"·"합치기": `.scratch/core`, `.scratch/search-eval` 등에 있는 "되돌려"(원상 복구)와 "합치기"(한데 모으기)는 이 이름과 무관한 보통 낱말이다. 정규식 `되돌려\s*합`이 걸리지 않아 바뀌지 않았다.

## 옛 이름의 잔존

찾은 명령과 결과다.

- `git grep -n --untracked -P "루트\s*브랜치|되돌려\s*합" -- . ':!docs/journal' ':!.venv' ':!evals' ':!.scratch/glossary-names-input.md' ':!.scratch/dev-branch'`. 일치한 파일은 위 "바꾸지 않고 남긴 것"의 기록, ADR 본문, 프로브, 옛 이름을 일부러 적은 곳, 이 티켓뿐이다. 이 명령은 줄 단위라 줄바꿈으로 갈라진 꼴을 못 잡는다. 처음에는 `git grep -P -z`로 갈라진 꼴을 찾았다고 적었으나 그 명령은 출력이 비어 있었고 실제로는 동작하지 않았다(영어 이름 `root branch`, `merge back`을 찾은 일치 없음 결과만 맞았다). 그 틈에서 `tools/check_ticket.py` 독스트링 105~106행의 "main→dev 되돌려⏎합치기"가 남았고, 셀프 리뷰 표준 축이 `git grep --untracked -n -E "되돌려$"`로 찾아 냈다(아래 셀프 리뷰). 고친 뒤 여러 줄 정규식 `되돌려\s*\n\s*(#\s*|//\s*|\*\s*|>\s*)?합|루트\s*\n\s*(#\s*|//\s*|\*\s*|>\s*)?브랜치`를 Grep 도구(`multiline: true`, `*.{py,md,toml,yml,yaml,json,ps1,txt}`)로 저장소 전체에 쳐서 일치 0건을 봤다.
- 줄여 부른 꼴로 `루트.{0,8}브랜치`와 `브랜치.{0,4}루트`를 찾아 읽었다. 일치는 모두 주 체크아웃을 줄여 부른 "루트"가 브랜치 이야기와 같은 문장에 있는 곳이다(스킬의 "루트의 브랜치", 도구 독스트링의 "루트가 다른 브랜치에 있을 때").
- `주 체크아웃이 따르는 브랜치` 앞뒤의 어미 변화 꼴로 `운영에서 개발로 합(친|칠|쳤|쳐)`를 찾아 `next-session/SKILL.md`의 "합칠 것이 남았다" 한 곳만 걸렸고 문장을 읽어 맞았다.
- 시험 이름을 바꾸지 않았으므로 시험을 이름으로 골라 돌리는 설정(변이 표, `-k`)이 옛 이름을 가리킬 일이 없다. `tools/mutate.py` 표와 `pyproject.toml`에서 두 이름을 찾았고 일치가 없었다.

## 검증

- `uv run ruff check .`은 처음에 줄 폭을 넘은 주석 둘(`tools/check_ticket.py` 192행, `tests/tools/test_check_ticket.py` 1115행, 각 102·106칸)을 잡았다. 새 이름이 길어서 생긴 일이다(받은 지시문 5-1이 알린 꼴이다). 주석을 두 줄로 나눠 고쳤고 다시 쳐서 `All checks passed!`다.
- `uv run ruff format --check .`은 `742 files already formatted`, `uv run pyright`는 `0 errors, 0 warnings, 0 informations`, `uv run lint-imports`는 계약 둘이 kept이고 broken이 0이다.
- `uv run python tools/check_instructions.py`, `uv run python tools/check_adr_pointers.py`, `uv run python tools/plan_table.py --check`는 출력 없이 끝났다(각각 따로 쳤고 종료 코드 0).
- `uv run python tools/sibling_overlap.py`는 번호 겹침이 없고(이 브랜치의 새 번호는 헌법 1.3.8) 형제 워크트리 `release-image-tickets`가 `.scratch/release-image/spec.md`를 함께 고치고 있다고 알렸다. 그 형제의 파일을 Grep으로 읽으면 같은 세 줄에 옛 이름이 그대로 있어(`되돌려 합` 세 곳) 그 형제가 이 줄들을 바꾸지는 않았다. 병합 충돌은 그 형제가 나중에 병합할 때 같은 파일의 이웃 줄이 겹치면 날 수 있고, 이 PR은 그 줄만 바꿨다.
- 바꾼 도구 파일의 시험 `tests/tools/test_check_ticket.py`, `test_hook_git_main_commit.py`, `test_run_hooks.py`를 `-p no:xdist`로 따로 돌려 `197 passed in 244.87s`였다. 이 PR은 코드를 바꾸지 않았으나 커밋에서 pre-commit의 검사 러너가 전체 pytest를 돈다. 그 결과는 아래 "커밋" 절에 적는다.

## 셀프 리뷰

`code-review` 스킬로 돌렸다. 범위는 base `d0bf91b`(`origin/dev`), 수정 파일 18개, 미추적 파일 둘(티켓과 이 일지), 커밋 0개였다. 표준 축은 Sonnet 5.5 / high 서브에이전트, 명세 축은 이 세션의 모델을 이은 서브에이전트가 돌았다. 이 변경은 이름만 바꾸고 절차와 상태 전이를 바꾸지 않아 갈래 밟기 문단과 명세 축의 (d) 줄은 브리프에 넣지 않았다. 보고는 받은 턴에 아래로 옮겼다.

### 표준 축

| 지적 | 판정 | 반영 |
|---|---|---|
| Major. `tools/check_ticket.py` 독스트링 105~106행의 "main→dev 되돌려⏎합치기"가 줄바꿈으로 갈라져 한 줄짜리 정규식을 지나갔다. 그래서 일지의 "줄바꿈 꼴은 일치가 없었다"도 거짓이었다 | 맞다. `git grep --untracked -E "되돌려$"`와 Grep 도구의 여러 줄 정규식이 같은 한 곳을 냈다 | 독스트링을 새 이름으로 맞추고(인용 `"티켓 검사와 봇"`은 한 줄에 둔다) `ruff check`로 줄 폭을 확인했다. 일지의 잔존 절을 사실대로 고쳤다. 고친 뒤 여러 줄 정규식 일치는 0건이다 |
| Minor (Shotgun Surgery). 이름 하나가 18곳에 흩어져 누락이 생겼다 | 남겼다 | 이름 바꾸기의 본질이라 고칠 대상이 아니고, 잔존 검사 방법의 문제다. 줄 끝 패턴(`되돌려$`)과 여러 줄 정규식으로 찾는 방법을 대기열 항목 `rename-sweep-misses-forms`에 더할 만하다. 항목을 더하는 일은 retro가 판정한다 |
| Nit. 새 이름이 길어 `tools/check_ticket.py`와 테스트 주석이 두 줄로 갈렸다 | 남겼다 | 읽는 데 문제가 없고 줄 폭 검사를 지난다 |
| Nit. `directive.md`와 `open-session`의 고쳐 쓴 문장에서 같은 문장 안에 새 이름과 단독 "루트"가 섞여 읽기 불편하다 | 남겼다 | 단독 "루트"(주 체크아웃을 줄여 부른 말)는 지시문 1-1이 바꾸라 한 이름이 아니고 시험이 그 문구를 맞댄다. 문장은 순환 정의가 아니다 |

표준 축이 밀 주장 (가)~(마)도 쳤다. 일지가 든 예외 밖에 걸리는 옛 이름은 위 줄바꿈 꼴 한 곳뿐이었고, `tests/tools/test_hook_prompt_directive.py` 385·386행의 `주 체크아웃 미갱신: 루트는 <브랜치>`, 스킬 절 이름의 따옴표 인용, `git diff --stat`의 수(18개 파일, 72줄 추가, 62줄 삭제)가 맞았다.

### 명세 축

| 지적 | 판정 | 반영 |
|---|---|---|
| 일지에 옮긴 첫째 선택지 설명 끝의 "(지금 형제 겹침 검사는 겹침이 없다고 합니다)"가 브리프에 준 원문에 없다 | 맞지 않다. 이 세션이 올린 선택 화면의 첫째 선택지 설명이 그 괄호로 끝났고, 브리프의 원문 사본이 그 괄호를 빠뜨린 것이다. 질문과 둘째·셋째 설명도 올린 글과 대조했다 | 일지는 그대로 둔다 |
| 일지가 operations.md에 "되돌려 합치기"가 11곳이라 적었으나 기준 SHA의 파일에서 "되돌려 합치기"는 9곳이고 "되돌려 합…"의 모든 꼴이 11곳이다 | 맞다. `git show d0bf91b:docs/constitution/operations.md`에서 `grep -o`로 9곳과 11곳을 셌다 | 일지의 수를 "되돌려 합…" 꼴 11곳(되돌려 합치기 9곳)으로 고쳤다. 합계 13은 그대로다 |
| 일지가 `tidy-checkouts`의 자리 표시를 여덟 곳이라 적었으나 옛 `<루트 브랜치>`도 새 `<주 체크아웃이 따르는 브랜치>`도 일곱이다 | 맞다. 기준 SHA의 파일과 지금 파일에서 `grep -o`로 일곱씩 셌다 | 일곱 곳으로 고쳤다 |
| 일지의 형제 워크트리 `release-image-tickets` 서술은 워크트리 밖이라 검증하지 못했다 | 사실이다. 그 파일은 Grep 도구로 읽어 옛 이름 세 줄이 그대로임을 봤고, git으로는 그 워크트리를 읽지 않았다 | 일지의 서술은 Grep으로 읽은 것이라고 이미 적었다. 그대로 둔다 |

명세 축은 범위 넘침이 없고, 헌법 버전 줄이 `docs/constitution/README.md` 하나에서 1.3.8이며, 헌법 파일 변경이 `operations.md`와 README 둘뿐이고, ADR 0016·0020 본문이 그대로이며, 단독 "루트"와 시험이 맞대는 문구가 그대로임을 확인했다고 보고했다.

### 고친 것, 남긴 것, 다시 돌린 명령

- 고친 것: 위 표의 맞다 판정 전부(독스트링 한 곳, 일지의 잔존 문장, 수치 둘). 새로 쓴 사실 문장은 세 가지로, 기준 SHA의 `operations.md`에서 "되돌려 합치기"가 9곳이고 "되돌려 합…"이 11곳이라는 것, `tidy-checkouts`의 자리 표시가 옛 새 모두 일곱 곳이라는 것, 여러 줄 정규식을 저장소 전체에 쳐서 일치가 0건이라는 것이다. 이 셋은 PR 직전 리뷰에 밀 주장으로 넘긴다.
- 남긴 것: 위 표의 Minor 하나와 Nit 둘, 그리고 판정이 맞지 않다고 한 하나(선택지 설명의 괄호).
- 다시 돌린 명령: 고친 뒤 `uv run ruff check tools/check_ticket.py`가 `All checks passed!`다. 손으로 치는 검사 다섯은 커밋이 부르는 pre-commit의 결과로 갈음한다.
