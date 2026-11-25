# session-asks-extractor: 세션 기록에서 선택 화면의 질문·선택지·답과 서브에이전트의 브리프·보고를 뽑는 도구를 저장소에 둔다

**What to build:** `tools/extract_asks.py`를 새로 둔다. 세션 기록 파일(JSONL)을 읽어 둘을 글로 낸다.

1. `asks`: `AskUserQuestion` 호출을 질문 하나씩 낸다. 질문 글, 선택지마다 라벨과 설명(미리보기가 있으면 그것도), 사용자의 답을 낸다. 답은 셋으로 가른다. 선택지를 골랐으면 그 라벨, 선택지에 없는 글을 직접 쳤으면 그 원문, 호출을 거부했거나 기록에 결과가 없으면 그렇다고 적는다. 답에 붙은 메모(`annotations`)도 낸다.
2. `agents`: 서브에이전트에게 준 브리프(`Agent` 호출의 `prompt`)와 돌아온 최종 보고를 낸다. 보고는 `queue-operation`의 `<agent-message from="…">` 글에서 하네스가 붙인 머리와 들여쓰기를 걷어 원문 그대로 낸다.

**왜.** `grilling`은 답을 일지·명세·ADR로 옮길 때 고른 선택지의 설명을 글자 그대로 옮기라고 한다. 그런데 그 글을 세션 기록에서 꺼내는 스크립트가 저장소에 없어서, 설계 인터뷰 세션마다 스크래치패드에 새로 썼다(대기열 `extract-asks-tool`의 승인 줄이 아홉 번을 센다). 세션이 끝나면 스크립트가 사라지고, core 설계 세션의 첫 판은 직접 친 답을 호출 전체의 답으로 잘못 붙여 틀렸다. 세션 기록은 컨텍스트가 압축된 뒤에도 압축 전의 줄을 그대로 갖고 있어서, 압축으로 사라진 질문의 글과 보고를 되찾는 길은 이것뿐이다.

**서브에이전트 보고까지 맡기는 판정.** 맡긴다. 까닭은 셋이다. (1) 세션 기록을 줄 단위로 읽고 호출과 결과를 짝짓는 뼈대가 같다. (2) `extract-asks-tool` 7회차가 질문 글과 서브에이전트 보고를 같은 세션에서 따로 스크래치 스크립트로 꺼냈고, `review-report-journal-lag` 10회차가 보고가 온 턴에 압축이 끼어든 것이라 받은 턴에 옮기라는 문장을 어디에 더하든 이 갈래에는 닿지 않는다고 적고, 반영할 때 세션 기록에서 보고를 꺼내는 일을 `extract-asks-tool`의 도구가 함께 맡는 길을 보라고 했다. (3) 보고만 따로 꺼내는 도구를 또 두면 같은 파일 읽기 코드가 둘이 된다. 이 티켓은 도구만 두고, "받은 턴에 일지로 옮기라"는 문장을 스킬과 에이전트에 다는 일은 하지 않는다. 그 일은 나란히 여는 `review-report-to-journal-on-receipt` 티켓 몫이라 겹치지 않는다.

**세션 기록의 모양(열어 보고 짠 것).** 2026-11-25에 이 저장소의 기록 폴더(`~/.claude/projects/C--project-rag-engine/`)의 모든 `*.jsonl`을 스크래치 스크립트로 훑어 줄의 종류와 결과 모양을 세고, 그 가운데 몇 개를 열어 줄을 읽었다(Claude Code 2.1.309 기록 포함). 커밋한 프로브가 아니라 손으로 본 것이다.
- 호출은 `type: assistant`인 줄의 `message.content`에 `tool_use`(이름 `AskUserQuestion`, `input.questions[]`)로 있다. 같은 호출이 `type: api-request-blob`인 줄과 같은 줄의 `wireToolInputs`에도 되풀이되므로, `assistant` 줄만 읽는다.
- 결과는 `type: user` 줄의 `tool_result`(`tool_use_id`가 호출 id)다. 같은 줄의 `toolUseResult`가 `questions`(선택지의 `label`·`description`·`preview`가 온전히 든다), `answers`(질문 글 → 답), 있으면 `annotations`(질문 글 → `preview`·`notes`)를 갖는다. `answers`의 값은 보통 문자열이고, 여러 개를 고르는 질문은 문자열 목록으로 오는 줄도 있었다.
- 직접 친 답은 `answers`에 선택지에 없는 문자열로 온다. 거부한 호출은 `tool_result.is_error`가 참이고 `toolUseResult`가 문자열 `User rejected tool use`다.
- 서브에이전트는 `Agent` 호출이 `async_launched` 결과(`toolUseResult.agentId`, `prompt`, `description`)를 먼저 돌려주고, 보고는 나중에 `type: queue-operation`의 `operation: enqueue` 줄(`content`가 `<agent-message from="<agentId>">`로 시작)로 온다. 같은 보고가 `queue-operation`의 `remove` 줄, `attachment`의 `queued_command`, 다른 도구 결과 속 `system-reminder`에도 되풀이된다. 하네스가 보고의 모든 줄을 두 칸 들여 쓰고 머리 문단(`The report follows:`까지)을 붙인다.

**대기열:** extract-asks-tool, review-report-journal-lag

이 티켓은 `extract-asks-tool`을 닫는다(도구와 `grilling`의 포인터 한 줄이 처방의 전부다). `review-report-journal-lag`는 10회차 갈래(보고가 온 직후 압축)의 몫인 "세션 기록에서 보고를 꺼내는 길"만 반영하고 열어 둔다. 그 항목의 승인 줄에는 나란히 여는 `review-report-to-journal-on-receipt` 티켓이 같은 줄을 고쳐 병합 충돌이 나기 쉬워서, 이 티켓은 그 파일을 고치지 않는다. 반영한 몫은 `extract-asks-tool`의 닫힘 줄에 적고, `review-report-journal-lag`의 승인 줄에는 retro가 옮긴다.

**Status:** done

- [x] `tools/extract_asks.py`가 `asks <세션 기록>`으로 `AskUserQuestion` 호출마다 질문 글, 선택지의 라벨·설명·미리보기, 답(고른 라벨, 직접 친 원문, 거부, 결과 없음)과 메모를 낸다. 한 호출에 질문이 여럿이면 질문 단위로 나눠 낸다. 여러 개를 고르는 질문은 고른 라벨들과 직접 친 글을 가른다
- [x] `agents <세션 기록>`이 브리프와 보고를 에이전트 하나씩 짝지어 낸다. 같은 보고가 여러 줄에 되풀이돼도 한 번만 낸다. 보고에서 하네스의 머리 문단과 들여쓰기를 걷는다. 보고가 아직 없는 에이전트는 없다고 적는다
- [x] 번호를 주면(`--only N`) 그 호출(`agents`는 그 에이전트)만 낸다. 호출이 하나도 없거나 번호가 범위 밖이면 이유를 적고 종료 1이다. 파일을 열지 못하거나 인자가 틀리면 종료 2다. 읽지 못한 줄이 있으면 그 수를 끝에 적는다
- [x] 출력이 한글로 깨지지 않는다(표준출력을 UTF-8로 맞춘다. `-X utf8` 없이 `uv run python tools/extract_asks.py …`로 쳐도 같다)
- [x] 모듈 독스트링에 무엇을 뽑는지와 **못 보는 것**을 적는다. 못 본다고 적은 것마다 시험 하나가 그 입력을 고정한다
- [x] `tests/tools/test_extract_asks.py`가 실제 기록 모양을 줄인 입력(여러 질문, 직접 친 답, 거부, 중복 줄, 압축 경계 앞뒤, 여러 개 고르기, 에이전트 보고의 되풀이)으로 위를 고정한다. 실제 기록 하나에 손으로 돌려 나온 호출 수·질문 수·답 수를 이 티켓의 Comments에 적는다(기록은 저장소에 없는 개인 파일이라 시험이 아니라 손으로 본 것이다)
- [x] 변이 파일 `.scratch/harness/probes/extract_asks_mutations.toml`이 도구의 판정(`assistant` 줄만 읽기, 답 가르기, 중복 걷기, 거부 판정)을 하나씩 깨고 시험이 빨강이 되는 것을 본다
- [x] `.claude/skills/grilling/SKILL.md` "옮길 때" 문단 끝에 포인터 한 줄이 있다(도구 이름과 부르는 법만. 도구의 규칙을 되풀이하지 않는다). 스킬 머리 주석(센티널)의 "더했다" 목록이 이 줄을 담는다
- [x] 대기열 항목 `extract-asks-tool`의 상태가 `닫힘 (…)`이고, 닫힘 줄에 이 티켓의 경로와 날짜와 한 것(서브에이전트 보고까지 맡긴 판정 포함)과 `review-report-journal-lag` 10회차에 반영한 몫이 적혀 있다
- [x] 지침 검사(`tools/check_instructions.py`)와 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(테스트는 커밋의 pre-commit이 갈음한다)

## Comments

**실제 기록에 손으로 돌린 것(2026-11-25, `uv run python tools/extract_asks.py …`, 커밋한 프로브가 아니라 손으로 본 것이다).**
- `asks`, 기록 `56918e8d-…jsonl`(2026-11-09 core 설계 인터뷰): 호출 23개, 질문 67개. 답은 고른 것 40, 직접 입력 23, 거부 4(거부한 호출 하나가 질문 넷). 스크래치 스크립트로 따로 센 값(`tool_result` 23개, 그 가운데 구조 있는 답 22, 거부 1)과 호출 수가 같고, 구조 있는 호출의 질문 수(67 - 4 = 63)가 고른 것과 직접 입력의 합(40 + 23)과 같다. 직접 입력 스무 개를 눈으로 훑어 선택지 라벨이 직접 입력으로 잘못 갈린 것은 없었다.
- `asks`, 기록 `02c9c047-…jsonl`(2026-11-20 source-sync 설계): 호출 7개, 질문 22개.
- `agents`, 같은 기록: 에이전트 다섯, 모두 브리프와 보고가 짝지어 나왔다. 처음 돌렸을 때 이름(`name: review-standards`)을 붙여 띄운 둘이 브리프만 있고 보고가 없는 줄과, 보고만 있고 브리프가 없는 줄로 갈렸다. 보고가 에이전트 id가 아니라 그 이름으로 돌아와서였다. 이름으로도 묶도록 고치고 시험 둘을 더했다.
