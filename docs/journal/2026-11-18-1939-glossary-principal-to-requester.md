# glossary-principal-to-requester: 용어집의 "주체"를 agent-os의 결정에 맞춰 "요청자"로 바꾼다 · 2026-11-18

앞 세션(일지 `2026-11-18-1817-glossary-harness-small-names.md`)이 PR 68을 병합하고 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-principal-to-requester.md`, 브랜치는 `chore/glossary-principal-to-requester`이고, 새 워크트리 `glossary-principal-to-requester`에서 `origin/dev`(89cf796)로 브랜치를 따서 했다. 용어집의 이름을 agent-os의 결정에 맞추는 일(받은 지시문의 원문 `.scratch/glossary-names-input.md`. 아래에서 "받은 지시문"은 이 글이다)의 셋째 PR이고, 받은 지시문 5-2의 차례 2다. 계기, 세션을 열며 한 정리, 물은 것과 사용자의 답, 한 것, 바꾸지 않고 남긴 것, 옛 이름의 잔존, 검증을 차례로 두고, 그 뒤의 리뷰와 회고는 한 차례씩 덧붙인다.

## 계기

사용자가 아래 지시문을 첫 메시지로 넣어 이 세션을 열었다. 줄 구성은 그대로이고, 긴 줄은 줄임 없이 옮겼다.

```
용어집의 "주체"를 "요청자"로 바꾸는 PR(받은 지시문 5-2의 차례 2)을 티켓 .scratch/harness/issues/glossary-principal-to-requester.md로 쓰고 한다

다음 작업: 받는 세션이 쓸 .scratch/harness/issues/glossary-principal-to-requester.md. 받은 지시문 `.scratch/glossary-names-input.md` 5-2의 차례 2다. 용어집의 "주체"(검색을 요청한 쪽의 신원)를 "요청자"로 바꾸고 "익명 주체"는 "익명 요청자"로 바꾸며, 살아 있는 글의 같은 말을 맞춘다(그 파일 1-3절). 피할 말 줄에는 옛 이름 "주체"를 더한다.
다음 단계: 구현
어디서: 새 세션. 주 체크아웃 미갱신이라 Skill 도구로 tidy-checkouts를 먼저 돌고(그 스킬이 사람에게 넘기는 것은 보고만 하고 답을 기다리지 않는다) 그 뒤 주 체크아웃에서 브랜치를 따지 않고 EnterWorktree(name은 glossary-principal-to-requester)로 새 워크트리에 먼저 들어가 거기서 브랜치를 바꾼다
시작 프롬프트: 용어집의 "주체"를 "요청자"로 바꾸는 PR(받은 지시문 5-2의 차례 2)을 티켓 .scratch/harness/issues/glossary-principal-to-requester.md로 쓰고 한다
브랜치: chore/glossary-principal-to-requester
모델: Sonnet 5.5 / high
읽을 것: docs/journal/2026-11-18-1817-glossary-harness-small-names.md의 "물은 것과 사용자의 답"(이름을 선택 화면으로 묻고 바꾸는 방식), .scratch/glossary-names-input.md의 1-3·5-1·5-2·5-3절, docs/agents/issue-tracker.md
이어받을 상태: 앞 차례 PR(`glossary-harness-small-names`)은 dev에 병합되었다. "주체"는 헌법 원칙 III과 V의 본문에도 쓰여 있다. 헌법 문구는 ADR과 사용자 승인으로만 고치므로(CLAUDE.md 작업 규약 5, 헌법 거버넌스) 그 문장을 바꿀지는 선택 화면으로 사용자에게 묻고, 바꾸면 헌법 판 규칙(`docs/constitution/README.md`)을 따른다. 코드 식별자와 ADR 결정의 제목은 바꾸지 않는다. 앞 PR의 회고가 올린 대기열 항목 `rename-sweep-misses-forms`는 이름 바꾸기 훑기에서 놓친 꼴을 다루므로 이번 훑기에 참고하고, 커밋 제목은 72자 안에 둔다(`commit-msg-after-slow-checks`가 5회차다).
확인할 선행 조건: 주 체크아웃 미갱신: 루트는 dev. 추적하지 않는 파일 둘이 루트를 깨끗하지 않게 하면 tidy-checkouts가 루트를 당기지 못한다. 병합은 이 워크트리 사본의 next-session merge.md(없으면 SKILL.md)의 "워크트리에서 병합할 때"를 Read로 열어 따른다. 형제 워크트리 `release-image-spec`(PR 67)이 열려 있어 겹치는 파일이 있으면 `uv run python tools/sibling_overlap.py`가 알린다
이번 요청 범위: PR과 병합까지
```

이 일은 retro가 승인한 대기열 항목이 아니라 사용자의 직접 지시다. 티켓의 대기열 줄에는 `glossary-plain-names-left`(이름을 바꾸는 일 전체)와, 지시문이 참고하라고 한 `rename-sweep-misses-forms`를 적었다.

## 세션을 열며 한 정리

지시문대로 이 세션의 제목을 브랜치 이름으로 바꾸고(`set_session_title`) `tidy-checkouts` 스킬을 먼저 돌렸다. 이 세션은 주 체크아웃(`C:\project\rag-engine`)에서 열렸고 `git fetch origin`을 쳤다.

- 주 체크아웃은 당기지 못했다. 루트는 dev이고 `HEAD`는 6957194, `origin/dev`는 89cf796이며, 원격에 없는 로컬 커밋은 0개다. `git status --porcelain`에 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 나와 깨끗하지 않았다. 스킬의 "루트 브랜치인데 깨끗하지 않다" 갈래라 건드리지 않았고, 지시문의 "이어받을 상태"가 이미 알린 파일이다.
- 지운 워크트리와 브랜치는 없다. `judge`가 `지운다`를 하나도 내지 않았다.
- 남긴 워크트리와 이유는 다음과 같다. `05-full-run-rerank`는 그 폴더를 작업 디렉터리로 쥔 프로세스(tail.exe, grep.exe, cut.exe)가 있다. `10-public-docs-questions`는 바뀐 파일이 있다. `13-first-judge-run`은 세션 `local_a6780d9a-3397-4c26-babc-619f7a2ab4e6`의 python.exe 열둘이 쥐고 있다. `16-search-latency-probe-f30c20`과 `relaxed-grothendieck-e892b9`는 앱의 표지가 있어 앱의 정리에 맡긴다. `glossary-harness-small-names`와 `release-image`는 그 브랜치가 제목인 세션이 돈다. `glossary-release-names`는 세션 `local_d605c69c-55e7-4ac6-9a61-d5ff9d365269`의 claude.exe 등이 쥐고 있다. `release-image-spec`과 `release-search-eval`은 병합된 PR이 없다.
- 사람에게 넘긴 것은 워크트리 `14-reindex-version-switch` 하나다. 병합된 PR의 머리와 브랜치 끝이 다르다. 앞 세션들도 같은 것을 넘겼고, 지시문대로 보고만 하고 답을 기다리지 않았다.
- 휴지통은 비우지 못했다. `empty-trash`를 쳤고 `.venv` 폴더 일곱이 남았다(앞 세션과 같은 일곱). 모두 `.pyd` 파일 하나에서 접근이 거부됐다(WinError 5). 다음 정리가 다시 본다.

그 뒤 `EnterWorktree`(name `glossary-principal-to-requester`)로 새 워크트리에 들어갔다. 워크트리의 시작 커밋은 89cf796(`origin/dev`)이었고, `git branch -m`으로 브랜치 이름을 `chore/glossary-principal-to-requester`로 바꾸었다(추적 브랜치가 아니라 푸시가 dev로 갈 길이 없다).

## 물은 것과 사용자의 답

받은 지시문 1절은 이 이름을 사용자에게 다시 묻지 않고 한다고 적었다. 새 이름 "요청자"는 사용자가 agent-os에서 이미 골랐으므로 묻지 않았다. 그러나 이 세션의 지시문이 헌법 문구는 사용자 승인으로만 고치므로 선택 화면으로 묻고 바꾸라고 적었고, "주체"는 헌법 원칙 III과 V, `docs/PRD.md`에 쓰여 있다. 화면을 올리기 전에 한 일은 옛 이름이 쓰인 곳을 `git grep`으로 세어 문맥을 읽은 것이다. 헌법과 PRD의 "주체"는 모두 요청한 쪽의 신원이라는 같은 뜻이었고, 원칙 III은 한 곳(MCP `_meta`에 실린 주체의 범용 형식), 원칙 V는 한 곳(접근 그룹을 쓰는 설치에서 주체가 없는 요청도 거부한다), PRD는 한 곳(1.0 목표 줄)이다.

질문은 하나였고 선택지는 셋이었다. 아래의 질문, 선택지, 설명은 이 세션에서 올린 글자 그대로이고, `> 사용자:` 줄이 답이다.

1. 질문(머리 `헌법 문구`)

   ```
   헌법 원칙 III과 V(두 곳)와 PRD의 1.0 목표 한 줄에 쓰인 "주체"를, 용어집과 똑같이 "요청자"로 바꿀까요? 이 말은 검색을 요청한 쪽이 누구인지 알리는 신원 정보를 가리킵니다.
   ```

   > 사용자: "바꾼다, 헌법 버전 1.3.7 (Recommended)"

   - 첫째 선택지 `바꾼다, 헌법 버전 1.3.7 (Recommended)`. 설명:

     ```
     문장에 넣으면 "MCP `_meta`에 실린 요청자의 범용 형식", "접근 그룹을 쓰는 설치에서는 요청자가 없는 요청도 거부한다", "문서 권한에 따른 검색(요청자가 없으면 거부)"이 됩니다. 뜻은 그대로이고 글자만 바뀌므로 헌법 버전은 문구 수정(patch)으로 1.3.6에서 1.3.7로 올립니다. 바뀌는 파일은 principles.md, PRD.md, constitution/README.md의 버전 줄 셋이고, 바꾼 까닭은 ADR 0014의 이력에 한 항목으로 남깁니다. 걸리는 점: 원칙 본문이 바뀌므로 헌법 버전이 하나 올라가고, 열려 있는 형제 브랜치가 같은 버전을 쓰면 번호를 비켜 가야 합니다(지금 형제 겹침 검사는 겹침이 없다고 합니다).
     ```

   - 둘째 선택지 `용어집과 살아 있는 글만 바꾼다`. 설명:

     ```
     헌법과 PRD는 "주체"로 두고, 용어집의 "주체" 항목을 "요청자"로 바꾸되 피할 말에 옛 이름 "주체"를 넣습니다. 헌법 버전은 그대로 1.3.6입니다. 걸리는 점: 원칙 III·V와 PRD에는 옛 이름이 남아, 용어집에서 "요청자"를 찾아 읽은 사람이 헌법에서 "주체"를 만나면 둘이 다른 것으로 읽힐 수 있습니다. 헌법을 바꾸는 일은 따로 한 번 더 PR을 내야 합니다.
     ```

   - 셋째 선택지 `지금은 정하지 않는다`. 설명:

     ```
     용어집만 바꾸고 헌법과 PRD는 건드리지 않으며, 헌법을 바꿀지는 대기열 항목 glossary-plain-names-left에 남겨 둡니다. 걸리는 점: 위 둘째 선택지와 같은 어긋남이 남고, 나중에 다시 사용자에게 묻는 일이 한 번 더 생깁니다.
     ```

### 답을 읽은 방식

- 사용자가 추천(첫째 선택지)을 골랐다. 그래서 두 곳의 "주체"를 "요청자"로 바꾸고 헌법 버전을 올렸다. 형제 겹침 검사(`tools/sibling_overlap.py`)는 형제가 쓴 가장 높은 헌법 버전을 1.3.6(`origin/dev`)이라 알렸고 번호 겹침이 없다.
- 선택 화면이 적은 대로 바꾼 까닭은 ADR 0014의 이력에 한 항목으로 남겼다. ADR 0014는 본문에 "주체(접근 그룹을 쓰는 설치에서 요청한 쪽의 신원)"가 든 ADR이다. 이 저장소의 ADR 가운데 "주체"가 든 것은 ADR 0014 하나다(`git grep`으로 찾았다). 본문은 글자 그대로 두었다. ADR 규칙(`.claude/rules/adr.md`)대로 이력을 더하기 전에 `domain-modeling` 스킬을 불렀고, 이름만 바뀐 이력이라 본문 문장을 거짓으로 만들지 않아 `(바뀜: …)` 포인터는 달지 않았다.

## 한 것

### 이름 바꾸기

옛 이름이 쓰인 살아 있는 글을 파일마다 문맥을 읽고 바꾸었다. 한 파일 안의 "주체"가 모두 같은 뜻(요청한 쪽의 신원)임을 읽은 뒤에 그 파일은 문자열 치환을 썼고, 뜻이 갈리는 파일은 직접 고쳤다.

| 파일 | 바꾼 것 |
|---|---|
| `GLOSSARY.md` | 항목 이름 주체 → 요청자, 풀이의 "주체가 없는 요청"과 접근 그룹 항목의 "어떤 주체가". 피할 말 줄에 `주체(옛 이름. 2026-11-18에 바꿨다)`를 더하고, 사용자의 까닭 괄호도 요청자로 맞췄다. 용어의 수와 차례는 그대로다 |
| `docs/constitution/principles.md` | 원칙 III과 V의 두 곳 |
| `docs/constitution/README.md` | 버전 줄 1.3.6 → 1.3.7 |
| `docs/PRD.md` | 1.0 목표 줄의 한 곳 |
| `docs/adr/0014-tokens-in-database-and-required-allowed-hosts.md` | 이력 절과 한 항목을 더했다. 본문은 그대로다 |
| `.claude/agents/spec-reviewer.md` | 원칙 위반 점검 문장의 한 곳 |
| `.coderabbit.yaml` | 권한 지침 문장의 한 곳 |
| `.github/PULL_REQUEST_TEMPLATE.md` | `server/` 검사 항목 문장의 한 곳 |
| `.scratch/doc-permission/plan.md` | 서른 곳(익명 주체 포함). 이 기능은 아직 todo다 |
| `.scratch/retro-queue/client-name-in-spec-body.md` | 열린 항목의 한 곳(주체 전달 설계) |
| `.scratch/retro-queue/glossary-plain-names-left.md` | 이름을 바꾸는 일의 진행을 적는 끝 문단에 이 티켓이 끝낸 일을 적고 남은 이름 목록에서 주체를 뺐다. 머리 줄과 `어디로:` 줄에서 주체를 아직 남은 일로 적은 문장도 끝났다고 맞췄다(명세 축 셀프 리뷰가 짚었다). `승인:` 줄의 `ADR 필요(판, 주체)`는 그때 받은 승인의 기록이라 두었다 |
| `.scratch/plan.md` | `uv run python tools/plan_table.py`로 다시 만들었다. 표의 doc-permission 행이 첫 줄을 따라 바뀌었다 |

조사는 바꿀 곳이 없었다. 옛 이름 "주체"와 새 이름 "요청자"는 끝 글자(체, 자)가 모두 받침이 없다. 확인으로 `요청자(은|이|을|과|으로|이라)`를 한글이 이어지지 않는 꼴로 추적 파일과 미추적 파일에서 찾았고, 받은 지시문의 설명 한 줄(이 이름이 틀린 조사 꼴을 예로 든 줄)만 걸렸다.

### 선택 화면에 보인 수와 실제로 바뀐 수

| 이름 | 화면에 보인 수 | 실제로 바꾼 파일 |
|---|---|---|
| 헌법과 PRD | 파일 셋(`principles.md`, `PRD.md`, 헌법 `README.md`의 버전 줄) | 셋. 같다 |
| 받은 지시문의 어림 | 9개 파일 49곳(지시문 1-3) | 이 PR에서 글자 "주체"가 "요청자"로 바뀐 파일은 `GLOSSARY.md`, `docs/constitution/principles.md`, `docs/PRD.md`, 지침 셋(`spec-reviewer.md`, `.coderabbit.yaml`, PR 템플릿), `doc-permission/plan.md`, 열린 대기열 항목 `client-name-in-spec-body.md`, 다시 만든 `.scratch/plan.md`로 아홉이다. 수가 지시문의 어림과 같지만 같은 파일은 아니다. 지시문의 아홉에는 기록인 `.scratch/kickoff-input.md`가 들어 있고 이 PR은 고치지 않았다. 수정 열둘은 이 아홉에 헌법 `README.md`(버전 줄만), ADR 0014(이력 절을 더했다), 대기열 항목 `glossary-plain-names-left`(진행 문단)를 더한 것이다. 새 파일은 티켓과 이 일지다 |

## 바꾸지 않고 남긴 것

`git grep`으로 옛 이름을 찾아(아래 "옛 이름의 잔존") 읽고 가른 것이다. 처음 훑은 정규식 `주\s*체`는 "주 체크아웃"에 걸려 결과가 너무 많았으므로 "체크"가 이어지는 꼴을 뺀 `주\s*체(?!\s*크)`로 다시 찾았다.

- 기록(끝난 기능의 명세와 티켓을 기록으로 보는 근거는 받은 지시문 머리의 어림 기준과 앞 두 PR의 티켓이다. `docs/constitution/operations.md`의 문서 위치 절과 README의 원천 표에는 "끝난 기능의 명세"를 기록으로 정한 문장이 없다): 일지 전부, 받은 지시문의 원문 `.scratch/glossary-names-input.md`, 킥오프 입력 `.scratch/kickoff-input.md`(31·195·239행), 끝난 기능 `core`의 명세 `.scratch/core/spec.md` 264행(`core` 계획에 끝 줄 2026-11-13이 있다), 끝난 티켓 `.scratch/harness/issues/glossary-release-names.md`와 `plain-words-in-written-artifacts.md`.
- 다른 뜻의 낱말: `.scratch/core/design/vector-store-comparison.md` 154행의 "유지 주체"(자료를 유지하는 쪽)는 보통 낱말이고 끝난 기능의 설계 문서다. `evals/public-docs/`의 법령 본문과 질의·근거 파일의 "주체"도 법령의 보통 낱말이라 평가 자료로 두었다. 자료 파일이라 손으로 고치지 않는다.
- 코드의 식별자와 `_meta`의 칸 이름: 이 저장소의 시험과 코드에는 "주체"가 없다. 식별자로서의 영어 `principal`은 `.scratch/core/probes/mcp-sdk/probe_sdk.py`와 `probe_out.txt`의 MCP `_meta` 칸 이름(`_meta.principal`)에만 있고 프로브라 두었다. 그 칸 이름을 적은 계약 문서는 아직 없다. ADR 0014 본문이 칸의 모양은 1.0 기능(doc-permission)의 설계가 정한다고 적었다. 처음에는 이 칸 이름을 계약에 적힌 식별자라고 적었으나 표준 축 셀프 리뷰가 그런 계약 문서가 없다고 짚어(`git grep _meta`가 ADR 0014와 원칙 문서에만 걸린다) 근거를 좁혔다. ADR 0014의 이력 항목과 티켓의 글도 같이 고쳤다. 이 티켓의 파일 이름과 그것을 가리킨 글(대기열 항목, ADR 0014의 이력)에도 `principal`이 글자로 들어 있지만 식별자가 아니라 파일 이름이다.
- 옛 이름을 일부러 적은 곳: `GLOSSARY.md`의 피할 말, ADR 0014의 이력 항목과 본문 22행(ADR 본문은 글자를 두고 이력으로 읽는다. 표준 축 셀프 리뷰가 이 줄이 목록에 없다고 짚었다), 대기열 항목 `glossary-plain-names-left`의 이름을 바꾼 일의 서술(옛 이름과 새 이름을 짝지어 적은 문단), 이 티켓과 이 일지.
- 클라이언트 쪽 용어는 건드리지 않았다. 바꾼 것은 이 서버의 한국어 글뿐이다.

## 옛 이름의 잔존

찾은 명령과 결과다.

- `git grep -n --untracked -P "주\s*체(?!\s*크)" -- . ':!docs/journal' ':!evals' ':!*.hwpx' ':!.scratch/glossary-names-input.md' ':!.venv'`. 일치한 파일은 위 "바꾸지 않고 남긴 것"의 기록, 다른 뜻의 낱말, 옛 이름을 일부러 적은 곳뿐이다. 살아 있는 글에서 뜻이 요청한 쪽의 신원인 "주체"가 남은 곳은 없다.
- 낱말 사이에 공백이 낀 꼴과 줄바꿈 꼴은 같은 정규식의 `\s*`가 잡는다. 줄여 부른 꼴과 영어 이름은 `principal`을 `git grep -i`로 찾았다(식별자로는 위 프로브 둘뿐이다. 이 티켓의 파일 이름을 가리킨 글에도 글자로는 들어 있다).
- `요청자(은|이|을|과|으로|이라)(?![가-힣])`는 받은 지시문의 설명 한 줄 외에 일치가 없다.

## 검증

- `uv run ruff check .`은 `All checks passed!`, `uv run ruff format --check .`은 `734 files already formatted`다.
- `uv run lint-imports`는 계약 둘이 kept이고 broken이 0이다. `uv run pyright`는 `0 errors, 0 warnings, 0 informations`다.
- `uv run python tools/check_instructions.py`, `uv run python tools/plan_table.py --check`, `uv run python tools/check_adr_pointers.py`는 출력 없이 끝났다(각각 따로 쳤다).
- `uv run python tools/sibling_overlap.py`는 번호 겹침이 없고 함께 고친 파일이 없다고 답했다. 이 브랜치의 새 번호는 헌법 1.3.7이다.
- 이 PR은 마크다운과 YAML 문구만 바꾸고 코드 동작을 바꾸지 않아, 전체 `uv run pytest`는 손으로 치지 않았다. 커밋에서 pre-commit의 검사 러너가 전체 pytest를 돈다. 그 결과는 아래 "커밋" 절에 적는다.

## 셀프 리뷰

`code-review` 스킬로 돌렸다. 범위는 base `89cf796`(`origin/dev`), 수정 파일 12개, 미추적 파일 둘(티켓과 이 일지), 커밋 0개였다. 표준 축은 Sonnet 5.5 / high 서브에이전트, 명세 축은 이 세션의 모델을 이은 서브에이전트가 돌았다. 이 변경은 이름만 바꾸고 절차를 바꾸지 않아 갈래 밟기 문단은 브리프에 넣지 않았다. 코드의 동작을 바꾸지 않아 상태 전이 갈래(d)도 넣지 않았다. 보고는 받은 턴에 아래로 옮겼다.

### 명세 축

| 지적 | 판정 | 반영 |
|---|---|---|
| Major. 일지가 선택 화면의 질문과 선택지를 글자 그대로 담지 않고 요지로 옮겼다(수용 기준 1) | 맞다 | 올린 질문, 선택지 셋, 설명 셋을 글자 그대로 옮기고 요지 문장은 걷었다 |
| Minor. 대기열 항목 `glossary-plain-names-left`가 머리 줄과 `어디로:` 줄에서는 주체를 아직 남은 일로 적는다 | 맞다 | 머리 줄과 `어디로:` 줄을 끝났다고 맞췄다. `승인:` 줄의 `ADR 필요(판, 주체)`는 그때 받은 승인의 기록이라 두었다 |
| Nit. `doc-permission/plan.md` 7행이 2026-11-11 선택지 설명을 풀어 쓴 문장까지 요청자로 바뀌었다 | 남겼다 | 따옴표로 감싼 인용이 아니라 풀어 쓴 문장이고 이 계획은 아직 todo인 살아 있는 글이다. 일지 `2026-11-11-1534-doc-permission-list-filter.md`의 원문은 "주체"로 읽는다 |
| Nit. 영어 `principal`이 프로브 둘에만 있다는 말이 느슨하다 | 맞다 | 식별자로는 프로브 둘뿐이고 파일 이름을 든 글에도 글자로 있다고 고쳤다 |
| 주장 검증 (나)의 부기: `operations.md` 문서 위치 절은 끝난 기능의 명세를 기록으로 정하지 않는다 | 맞다 | "바꾸지 않고 남긴 것"에 기록으로 보는 근거가 받은 지시문 머리의 어림 기준과 앞 두 PR의 티켓이라고 적었다 |

### 표준 축

| 지적 | 판정 | 반영 |
|---|---|---|
| Minor. 대기열 항목 `어디로:` 줄의 미래형 두 문장이 거짓이다 | 명세 축 둘째 지적과 같다 | 위와 같다 |
| Minor. ADR 0014 이력과 티켓과 일지가 `_meta`의 칸 이름을 "계약에 적힌 식별자"라고 썼으나 그런 계약 문서가 없다 | 맞다. `git grep _meta`가 ADR 0014와 원칙 문서에만 걸린다 | 근거를 프로브가 쓴 칸 이름으로 좁혔다. ADR 0014 이력은 칸의 이름과 모양을 본문대로 1.0 기능의 설계가 정한다고 적고, 티켓과 일지도 같게 고쳤다 |
| Minor. "바꾸지 않고 남긴 것"에 ADR 0014 본문 22행이 없다 | 맞다 | 일부러 적은 곳에 더했다 |
| Nit. 지시문의 9개 파일과 이 PR의 아홉이 우연히 같은 수라 일치로 읽힌다 | 맞다 | 두 아홉이 같은 파일이 아니라고 파일 이름으로 풀어 썼다 |
| Nit. "요청자"가 사람으로 읽히는데 풀이는 신원 정보라 한다(Mysterious Name) | 남겼다 | 사용자가 agent-os에서 이미 고른 이름이고 받은 지시문 1절이 다시 묻지 않는다고 한다. 용어집 풀이가 사람 자체가 아니라 요청에 담겨 온 신원 정보라고 가르는 문장을 피할 말 줄에 둔다 |
| Nit. 같은 문장이 일곱 곳에 복제돼 있다(Duplicated Code, Shotgun Surgery) | 남겼다 | 이 변경이 만든 문제가 아니라 문서에 이미 있던 복제이고, 이름을 바꾸는 일의 범위 밖이다 |

### 고친 것, 남긴 것, 다시 돌린 명령

- 고친 것: 위 표의 맞다 판정 전부(질문과 선택지 글자 그대로, 대기열 항목 문장 둘, `_meta` 칸 이름의 근거 셋, 남긴 곳 목록 하나, 파일 수 대조 풀이, 기록으로 보는 근거). 새로 쓴 사실 문장은 식별자로서의 `principal`은 프로브 둘뿐이라는 것, `git grep _meta`가 ADR 0014와 원칙 문서에만 걸린다는 것, 지시문의 아홉과 이 PR의 아홉은 같은 파일이 아니라는 것이다. 이 셋은 PR 직전 리뷰에 밀 주장으로 넘긴다.
- 남긴 것: 위 표의 Nit 셋과 판정. 이름 "요청자" 자체는 사용자가 고른 이름이다.
- 다시 돌린 명령: 고친 뒤 인용 대조와 지침 검사 등은 아래에서 다시 쳤다. 손으로 치는 검사 다섯은 커밋이 부르는 pre-commit의 결과로 갈음한다.
