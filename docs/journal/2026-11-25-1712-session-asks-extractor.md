# session-asks-extractor: 세션 기록에서 선택 화면의 질문·선택지·답과 서브에이전트의 브리프·보고를 뽑는 도구를 저장소에 둔다 · 2026-11-25

대기열 `extract-asks-tool`을 닫는 harness 티켓이다(`.scratch/harness/issues/session-asks-extractor.md`). 브랜치는 `chore/session-asks-extractor`(기준 `origin/dev`, `61847dd`), 작업은 같은 이름의 워크트리에서 했고 모델은 Sonnet 5.5 / high이다. `review-report-journal-lag` 10회차의 "보고를 꺼내는 길"은 같은 도구가 맡는 것으로 판정했다.

## 셀프 리뷰

`/code-review`를 기준 `61847dd`로 돌렸다. 범위는 수정 파일 둘(`grilling/SKILL.md`, 대기열 항목 `extract-asks-tool`), 미추적 파일 다섯(`tools/extract_asks.py`, `tests/tools/test_extract_asks.py`, 변이 표, 티켓, 이 일지), 커밋 없음이다. 표준 축은 `sonnet`·`high`로 돌렸고, 명세 축은 이 세션의 모델을 이어받았다.

### 표준 축 보고(받은 그대로)

Critical·Major 없음. 위반 Minor 셋, 주장 검증 Minor 여럿, 판단 항목 셋, Nit 둘이다.

**(a) 문서화된 표준 위반(Minor).**
1. 출력 인자. `CODING_STANDARDS.md`의 "출력 인자를 쓰지 않는다"에 걸린다. `_apply_result(call, record, part) -> None`(extract_asks.py:248)이 받은 `call`을 고치고, `collect_agents`도 `run.agent_id`와 `run.reports`를 제자리에서 고친다.
2. 실패 기대 시험의 까닭. "실패의 까닭까지 단언한다"에 걸린다. `test_main은_인자가_틀리면_2로_끝난다`는 `err != ""`만 본다.
3. 약한 단언. `test_선택지_설명과_질문_글을_글자_그대로_낸다`는 이름과 달리 출력에서 `"첫 줄입니다."` 부분 문자열만 본다. 긴 설명 전체가 글자 그대로 나오는지는 보지 않는다. 원문과 견주는 단언은 `indent_block`과 `unindent`의 왕복뿐이다.

**주장 검증.**
- 부르는 쪽의 길(9번): 모듈 독스트링은 "일지에 옮길 때는 들여쓰기를 걷고 옮긴다(`unindent`)"고 안내한다. CLI는 `unindent`를 노출하지 않고 프로덕션 코드에서도 부르지 않으며, 부르는 곳은 시험뿐이다. 시험도 CLI 출력에서 `unindent`로 원문을 되찾는 길은 밟지 않는다. 가능한 Speculative Generality이기도 하다.
- "읽지 못한 줄은 세어 출력 끝에 적는다"는 거짓이다. 전부 깨진 파일(깨진 줄 3개)을 `asks`로 돌리면 종료 1에 "호출이 없다"만 나오고 줄 수는 나오지 않는다(`agents`도 같다). 재현했다.
- 동기 에이전트: 독스트링은 "`async_launched`가 아닌 결과"에서 "도구 결과에 있다"고 적는다고 하나, 코드는 `status`가 아니라 `agentId`가 없을 때만 그렇게 적는다. 동기 결과가 `agentId`를 함께 가지면 `status: completed` 결과에서도 "보고가 기록에 없다"가 나온다(재현함). 기록에는 동기 사례가 없다.
- "이 저장소의 기록 80건은 모두 `async_launched`": 메인 폴더만 센 값이다. 워크트리 폴더까지 124개 파일을 세면 472건이 모두 `async_launched`다(스크립트로 쟀다). 방향은 맞지만 범위가 좁게 적혔다.
- 여러 보고가 한 줄에 든 경우: 한 `enqueue` 내용에 `</agent-message>`가 둘 있으면 `parse_handback`이 첫 보고에 둘째 메시지 전체를 넣는다(재현함). 실제 기록 81건에는 없었지만 "못 보는 것"에 없고 시험도 없다.
- `rejected`: `is_error` 결과나 문자열 `toolUseResult`는 모두 "사용자가 이 호출을 거부했다"로 적히고 결과 글이 버려진다. 기록에서 본 거부는 1건뿐이고 훅이 막은 경우는 못 봤다. 훅(`hook_choice_facts`)이 첫 화면을 막으면 사용자 거부로 오인될 수 있다고 코드를 읽고 판단한다.
- 같은 질문 글이 둘이면 합쳐진다. 답을 질문 글로 짝짓는 탓에 한 호출 안의 같은 질문 글 둘이 같은 답을 받는다(재현함). "못 보는 것"에 없다.
- "한 번씩 틀렸다"(독스트링)와 "매번 한 번씩 틀렸다"(티켓): 대기열 `extract-asks-tool`은 core 설계 세션의 첫 판 하나만 직접 친 답을 호출 전체의 답으로 붙여 틀렸다고 적는다. 다른 회차의 오류는 설명 누락이다. 과장이다(손으로 봤다, Grep).
- "못 보는 것"을 시험으로 고정하는 규칙(`tools.md`): `SendMessage`와 `subagents/` 파일을 읽지 않는다는 항목은 전용 시험이 없다. 비-Agent 도구 이름을 거르는 시험이 일부만 덮는다.
- 인용 `"구조가 없다"`, `async_launched`·`api-request-blob`·`wireToolInputs`는 코드와 기록에서 글자 그대로 확인했다. 69건과 2.1.309도 맞다.

**(b) 기준선 냄새(판단 항목, 위반 아님).**
- 가능한 Primitive Obsession: `AskCall.status: str`(네 값)이 문자열로 서 있다.
- 가능한 Data Clumps: `answers`, `notes`, `previews`가 질문 순서로 늘어선 병렬 리스트라 `_render_question`에서 `index < len(...)` 가드가 되풀이된다. 질문별 한 레코드로 묶는 길이 있다.
- Mysterious Name: `collect_agents`의 `by_agent`는 이름과 에이전트 id를 한 맵에 섞는다. 이름이 어떤 id와 같으면 충돌하고, 함수도 길고 중첩이 깊다.
- Nit: 시험 이름에 `main`이 들어가고(`test_main은_…` 일곱 개) 함수 이름이 새어 있다.
- Nit: `| head`로 파이프를 닫으면 윈도에서 stderr에 `OSError: [Errno 22]`가 찍힌다(손으로 봤다).

근거 종류: 스크립트로 쟀다는 위 "주장 검증"의 재현·집계 항목, 코드를 읽었다는 `rejected`의 훅 오인 가능성, 손으로 봤다는 대기열 대조와 Nit이다.

### 명세 축 보고(받은 그대로)

요구한 동작은 대부분 실제 기록에서 성립한다. 빠진 것이 하나, 옮겨 적은 인용이 글자와 다른 것이 둘, 사실 주장 틀림이 하나다.

**(a) 빠졌거나 부분인 것.**
1. 변이 표에 "`assistant` 줄만 읽기"가 없다. 수용 기준 "변이 파일 … 도구의 판정(`assistant` 줄만 읽기, 답 가르기, 중복 걷기, 거부 판정)을 하나씩 깨고 시험이 빨강이 되는 것을 본다". 변이 11개 가운데 `kind == "assistant"` 검사를 깨는 것이 없다. `collect_asks`의 그 검사를 `kind in ("assistant","api-request-blob")`로 바꾼 사본으로 `test_assistant_줄만_읽어_되풀이된_호출을_한_번만_센다`와 같은 모양을 돌렸더니 호출은 1개로 그대로였다(스크립트로 쟀다). 시험의 blob 줄이 같은 id라 id 중복 걷기가 가린다. 다른 id의 blob 줄을 넣으면 호출이 2개가 된다.
2. "못 보는 것"을 시험 하나씩으로 고정한다는 항목이 한 군데 비었다. 독스트링의 "`subagents/` 기록과 `SendMessage` 이어받기 글은 읽지 않는다"에는 전용 시험이 없다. 비-Agent 도구와 일반 큐 줄을 거르는 시험이 일부만 덮는다(표준 축 보고와 겹친다).
3. 읽지 못한 줄 수가 일부 출구에서 안 나온다. 수용 기준 "읽지 못한 줄이 있으면 그 수를 끝에 적는다". 호출이 없어서(종료 1) 끝나거나 번호가 범위 밖이면 줄 수를 안 적는다. 종료 0 길에서만 적는다. 줄 중간에 UTF-8로 못 읽는 바이트가 있으면 줄 수를 세지 않고 파일 전체가 종료 2다(코드를 읽었다: `read_records`, `main`).

**(b) 범위 넘침.** 거의 없다. `grilling` "옮길 때" 문단에는 "한 줄"이 아니라 두 문장이 붙었다. 포인터 문장 하나에 "스크래치패드에 추출 스크립트를 새로 쓰지 않는다"는 금지가 더해졌다. 경미하다.

**(c) 구현이 틀려 보이는 것.** 거부 판정이 넓다. 티켓 인용 "거부한 호출은 `tool_result.is_error`가 참이고 `toolUseResult`가 문자열 `User rejected tool use`다"인데, 코드는 `is_error`가 참이거나 `toolUseResult`가 아무 문자열이면 "사용자가 이 호출을 거부했다"고 적는다. 손으로 돌렸다(`edge.py`). 입력 검증 오류, 사용자 중단 문구, `is_error` 없는 문자열 결과가 모두 "거부됨"으로 나온다. 실제 기록 69건에는 거부 1건뿐이라 거짓 양성은 기록에서 본 적이 없다.

**주장 검증, 스크립트로 쟀다(맞는 것).** 호출 69건과 에이전트 결과 80건이 모두 `async_launched`다. 결과 모양은 구조 있는 답 68건(메모 칸이 든 것 5건 포함)과 거부 1건이다. 기록 버전에 2.1.309가 든다(2.1.321과 2.1.325 기록도 있다). `56918e8d`는 호출 23, 질문 67, 고른 것 40, 직접 입력 23, 거부 4로 티켓과 같다. 모든 기록에서 답이 없는 질문은 0, 선택지와 직접 입력이 동시인 답은 0이다. 선택지 라벨·설명·미리보기·직접 입력 158개 질문 전부가 출력에 글자 그대로 들어 있다(미리보기는 이중 들여쓰기로 나온다). 여러 개 고르기의 목록 모양 답(`30959f3d`)이 고른 라벨 넷으로 갈린다. 에이전트 80개 모두 브리프와 보고가 짝지어지고, 보고가 둘인 하나는 `SendMessage` 이어받기의 서로 다른 두 보고라 정당하다. 보고의 `enqueue` 줄은 81개이고 80개로 중복이 걷힌다. 종료 코드(번호 없음·범위 밖 1, 없는 파일·틀린 인자 2)와 `PYTHONUTF8` 없는 UTF-8 출력이 맞다. 출력 줄바꿈은 윈도에서 CRLF다. 닫힘 꼴과 `tools/check_instructions.py`(종료 0)가 맞다.

**틀린 사실 주장.**
1. 티켓 Comments의 "`asks`, 기록 `02c9c047-…jsonl`: 호출 22개"가 틀렸다. 호출은 7개이고 질문이 22개다. 질문 수를 호출 수로 적었다.

**따옴표 인용이 원문과 글자 그대로가 아닌 것(grep으로 봤다).**
2. 티켓의 `"받은 턴에 옮기라는 문장은 이 갈래에 닿지 않는다"`는 `review-report-journal-lag.md` 10회차 원문이 아니다. 원문은 "받은 턴에 옮기라는 문장을 어디에 더하든 이 갈래에는 닿지 않는다"다.
3. 대기열 `extract-asks-tool` 닫힘 줄의 `"보고가 온 직후에 압축이 끼는 갈래"`는 10회차에 그 낱말이 없다. 원문은 "보고가 온 턴에 압축이 끼어든 것"이다. 티켓 쪽의 같은 구절은 따옴표 없는 풀어 쓴 말이라 문제가 없다.
4. 티켓의 "이 도구가 보고를 꺼내는 길을 제안했다"는 약간 세다. 10회차는 보고를 파일로도 남기게 하는 길과 이 도구가 함께 맡는 길을 "본다"며 둘을 나란히 든다.

그 밖에 맞다고 확인한 인용은 `async_launched`, `The report follows:`, `User rejected tool use`, `<agent-message from="…">`, 승인 줄의 "아홉 번"(9회차), 7회차의 설명이 티켓 근거와 같은 것이다. 표준 축 보고와 겹치는 것은 "매번 한 번씩 틀렸다" 과장, `unindent`가 CLI 길이 아닌 것, 80건이 메인 폴더만 센 값인 것, 거부 판정이 넓은 것, 줄 수 미표기다.

근거 종류: 스크립트로 쟀다(리뷰어의 스크래치 스크립트 여덟), 손으로 봤다(CLI의 종료 코드와 UTF-8 출력, grep으로 한 인용 대조), 코드를 읽었다(`read_records`, `main`), 어림은 없다.

### 판정과 반영

**고친 것.** 표준 축과 명세 축이 같은 곳을 짚은 것은 한 번에 센다.
- 출력 인자(표준 a1): `_apply_result`를 `_with_result`로 바꿔 새 호출을 돌려주게 했다(`dataclasses.replace`). `collect_agents`는 에이전트마다 보고 목록을 쌓는 자리라 같은 방식으로 손보지 않고, 호출 하나의 상태를 바꾸는 쪽만 고쳤다.
- 실패 시험의 까닭(표준 a2): 인자가 틀린 시험이 `invalid choice: '모르는명령'`을 단언한다.
- 약한 단언(표준 a3): 긴 설명 전체가 `indent_block`을 두 번 거친 글로 나오는지, 질문 줄과 고른 선택지 줄이 있는지 단언한다.
- `unindent`(표준 주장 검증 9번): 부르는 곳이 시험뿐인 죽은 함수라 지웠고 독스트링은 "들여쓰기를 걷고 옮긴다"로만 적는다.
- 읽지 못한 줄 수(표준, 명세 a3): 종료 1의 오류 글 끝에도 `(읽지 못한 줄 N)`을 붙이고 `asks`와 `agents` 둘 다 시험으로 고정했다. UTF-8로 못 읽는 바이트가 든 파일은 줄 수를 세지 않고 종료 2라고 독스트링에 적고 시험을 더했다.
- 동기 에이전트(표준): 독스트링을 코드대로 고쳤다. `agentId`가 없을 때만 동기로 어림하고, 동기 결과가 `agentId`도 가지면 보고를 못 찾았다고 적는다.
- "80건"(표준): 메인 폴더 80건과 워크트리까지 472건을 함께 적고 리뷰어가 센 값임을 밝혔다. 티켓에서는 개수를 뺐다.
- 보고 둘이 한 줄(표준): 독스트링 못 보는 것에 적고 시험 `test_보고_글_하나에_메시지가_둘이면…`을 더했다.
- 거부 판정(표준, 명세 c): 거부는 `toolUseResult`가 `User rejected tool use`일 때만이고, 그 밖의 `is_error`·문자열 결과는 새 상태 `error`로 적고 결과 글을 붙인다. 시험 `test_거부가_아닌_오류_결과는…`과 변이를 더했다.
- 같은 질문 글 둘(표준): 독스트링에 적고 시험으로 고정했다.
- `SendMessage`(표준, 명세 a2): 독스트링 항목마다 시험이 하나 있어야 해서 `SendMessage` 이어받기 글을 에이전트로 세지 않는 입력을 기존 시험에 더했다.
- 변이 표에 `assistant` 줄만 읽기가 없던 것(명세 a1): 다른 id의 `api-request-blob` 줄을 넣어 시험을 고치고(같은 id 줄은 id 중복 걷기가 가렸다), 그 검사를 깨는 변이를 더했다. 거부 변이도 새 코드에 맞췄다.
- `grilling`의 금지 문장(명세 b): 포인터 한 줄이라는 티켓 기준에 맞게 "스크래치패드에 추출 스크립트를 새로 쓰지 않는다"를 지웠다.
- 인용과 수치(명세): 티켓 Comments의 `02c9c047`은 호출 7개·질문 22개로, 에이전트는 다섯으로 고쳤다. 10회차 인용은 원문 그대로 풀어 쓰고 "제안했다"는 "보라고 했다"로 고쳤다. 대기열 닫힘 줄의 틀린 인용은 따옴표를 걷고 "보고가 온 턴에 압축이 끼어든 갈래"로 고쳤다.
- "매번 한 번씩 틀렸다"(표준): 대기열 원문은 core 설계 세션의 첫 판 하나만 틀렸다고 적어 과장이었다. 티켓 "왜" 절의 문장을 "첫 판이 한 번 틀린 적이 있다"로 맞춘다(독스트링은 이미 그렇게 적었다).
- `by_agent`(표준 b): 이름과 id를 한 맵에 섞는 것은 같되 이름을 `by_address`로 바꿔 무엇을 담는지 드러냈다. 충돌(이름이 다른 에이전트의 id와 같음)은 사실상 일어나지 않는다고 보고 독스트링에 적지 않았다.

**남긴 것.**
- Data Clumps(`answers`·`notes`·`previews` 병렬 리스트): 질문별 레코드로 묶는 편이 낫지만 렌더러 둘과 시험 전체를 건드리는 크기라 이 티켓에서 뺀다. 쓰는 곳이 둘뿐이고 길이 가드가 시험으로 고정돼 있다.
- Nit(시험 이름에 `main`이 든 것, `| head`에서 윈도가 찍는 `OSError`): 시험 이름은 `tools/`의 선례(`test_main은…`)와 같아 그대로 두고, `| head`는 파이프를 닫는 쪽의 윈도 동작이라 도구에서 막지 않는다.
- Primitive Obsession(`status`): 이미 `Literal` 닫힌 목록이라 따로 타입을 두지 않는다.
- 동기 결과가 `agentId`도 가지는 갈래는 기록에서 본 적이 없어 시험 없이 독스트링의 어림으로만 적었다.

**다시 돌린 명령과 결과(2026-11-25, 반영 뒤).** `uv run ruff check .` 통과, `uv run ruff format --check .` 977개 모두 포맷됨, `uv run pyright` 오류 0, `uv run lint-imports` 계약 2개 유지, `tools/check_instructions.py`와 `tools/check_type_escapes.py` 출력 없이 통과, `tests/tools/test_extract_asks.py` 40개 통과, `tools/plan_table.py` 실행(변경 없음), `tools/mutate.py --check`로 변이 13개의 원문이 한 번씩 있음을 확인한 뒤 전체 실행해 13개 모두 기대대로 빨강이었다(표지는 시험 소스에 글자 그대로 있지 않은 실패 출력으로 했다). 전체 테스트(`uv run pytest`)는 커밋이 부르는 pre-commit이 갈음한다. 이 결과는 커밋 뒤 pre-commit 출력으로 확인해 이어 적는다.

**pytest 훅을 건너뛴 커밋(사용자 승인).** 커밋의 pre-commit 전체 시험을 네 번 돌렸고 모두 빨강이었다. 첫 번째는 `kiwipiepy` 토크나이저에서 xdist 작업자가 `Fatal Python error: Aborted`로 죽고 4200초 제한을 넘겼다. 나머지 셋은 5877~5885개가 통과하고 서버 쪽 시험이 4개, 12개, 8개 실패했다. 실패한 시험은 실행마다 달랐고(`test_admin_pull_source_stuck_calls.py`, `test_cleanup_round_trip.py`, `test_delete_restore.py`, `test_serve_command.py`, `test_first_round_trip.py` 등) 대부분이 1.0초 상한을 1.06~1.92초로 넘긴 시간 단언이거나 "serve가 30초 안에 뜨지 않았다", HTTP 연결 오류였다. 그때 이 PC의 CPU는 94~98%였고 다른 세션(`agent` 프로젝트의 pyright, 형제 워크트리의 pytest)이 쓰고 있었다. CPU가 55% 아래로 내려간 뒤에 한 번 더 돌렸으나 같은 모양으로 8개가 실패했다. 같은 시험을 `-n 0`으로 단독 실행(테스트 DB 붙임)하면 26개가 모두 통과했다(186초). 이 변경은 `src/`를 건드리지 않고 도구·시험·문서·변이 표만 더한다. 사용자가 "이번 커밋만 pytest 훅 건너뛰기"를 승인해 `SKIP=pytest`로 커밋하고, 전체 시험은 PR의 CI(`verify`)가 판정한다. 시간 단언 시험이 부하가 있는 병렬 실행에서 흔들리는 문제는 이 티켓의 몫이 아니라 남긴다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트를 `origin/dev`와 합친 뒤(`fc42c91`)에 돌렸다. 범위는 `origin/dev...HEAD`, 파일 7개다. 아래는 받은 그대로다(하네스가 붙인 두 칸 들여쓰기만 걷었다).

### 보고(받은 그대로)

## 실행 상태 (맨 앞)
- `Seat:` 줄: `Seat         : not assigned` (Plan: Free, CLI 0.7.5, `Review access` 아래). 종료하지 않고 3단계로 갔다.
- CLI는 끝까지 돌았다. `coderabbit review --agent --include-untracked --base origin/dev`가 종료 코드 0으로 끝나 `review_completed`(findings 1건)를 냈다. 리뷰 파일은 7개 전부다. 출력은 `C:\Users\User\AppData\Local\Temp\claude\e659c78be23187d6\d449d83d-da0e-46d6-a519-8325d1cd9cd4\scratchpad\cr.out`에 있다.
- 이 변경의 시험은 `uv run pytest -q -p no:cacheprovider -n 0 tests/tools/test_extract_asks.py`로 40개 통과를 확인했다. 전체 pytest는 돌리지 않았다.
- 코드는 고치지 않았다. 재현에 쓴 입력 파일은 모두 스크래치패드(`...\scratchpad\`의 gen.py, small.jsonl, big.jsonl, trunc.jsonl, par.jsonl)에만 만들었다.
- 셀프 리뷰 일지에 이미 있는 지적(BrokenPipe, 이름과 id가 한 맵에 섞임, 같은 질문 글 둘, `rejected` 오인 가능성, `subagents/` 시험 없음 등)은 다시 내지 않았다.

## 유효 (고칠 것)

### Major
- **[Major] `tools/extract_asks.py:523` (`print(text)`) — 기록에 짝 없는 서로게이트 문자(`\ud800`)가 든 글이 있으면 트레이스백을 내고 종료 1로 끝난다.**
  - 재현: 호출 줄 `{"type":"assistant","timestamp":"t","message":{"content":[{"type":"tool_use","id":"a1","name":"AskUserQuestion","input":{"questions":[{"question":"Q?","header":"H","multiSelect":false,"options":[{"label":"A","description":"d"}]}]}}]}}`와, 결과 줄 `{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"a1","content":"x"}]},"toolUseResult":{"answers":{"Q?":"\ud800 typed"}}}`를 이 순서로 한 파일에 쓰고(JSON 이스케이프 `\ud800`) `uv run python tools/extract_asks.py asks <파일>`를 돌린다. `UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' ... surrogates not allowed`가 나고 `echo $?`가 1이다.
  - 근거: `json.loads`는 `\ud800` 이스케이프를 받아들이는데 `stream.reconfigure(encoding="utf-8")`는 strict라 출력에서 터진다. 독스트링은 종료 1을 "낼 것이 없다"로 정의하는데 이 경우는 내용이 있는데 1로 끝나서, 부르는 쪽이 "없다"로 오독한다. 사용자가 직접 친 답이나 도구 결과 글이 서로게이트를 품는 일은 이모지 잘림 등으로 실제 기록에서 날 수 있다.
  - 제안: `reconfigure(encoding="utf-8", errors="replace")`(또는 `backslashreplace`)로 하고, `main`이 `UnicodeEncodeError`를 잡아 종료 2로 끝내게 한다. 서로게이트가 든 기록 한 줄을 넣고 종료 0과 출력을 단언하는 시험과 변이 하나를 더한다.

### Minor
- **[Minor] `tools/extract_asks.py:159-176` (`read_records`) — 기록을 줄 단위로 읽으면서도 파싱한 줄을 전부 리스트에 쌓아 둔다. 쓰지 않을 줄(큰 파일 읽기 결과, `api-request-blob`)까지 메모리에 남는다.**
  - 재현: 100KB짜리 `tool_result`+`toolUseResult` 줄 400개(파일 80MB)를 `read_records`에 넣으면 tracemalloc 최대치가 약 81MB이고 0.55초다. 곧 파일 크기만큼을 잡는다. 같은 호출이 `api-request-blob`과 `wireToolInputs`에 되풀이되는 실제 기록은 작은 객체가 많아 객체 오버헤드 때문에 보통 파일 크기의 몇 배다. 수십 MB는 괜찮지만 수백 MB 기록은 위험하다.
  - 근거: 필요한 것은 `assistant`의 `tool_use` 블록, `user`의 `tool_result`, `queue-operation`, `attachment`뿐이다. 읽는 줄 수와 시간은 문제가 아니다(파일을 통째로 읽는 곳은 없고 `for raw in handle`로 읽는다).
  - 제안: `read_records`를 생성기로 바꾸고, 파싱 전에 `type`이 네 종류가 아닌 줄을 버린다. 또는 파싱 뒤 필요한 필드만 남긴다. `collect_*`는 이미 한 번 훑는 구조라 바꾸기 쉽다.
- **[Minor] `tools/extract_asks.py:163`와 `:500` — 줄 끝이 UTF-8 중간에서 잘린 파일(세션이 아직 쓰는 중인 기록)이면 파일 전체를 못 읽고 종료 2로 끝난다.**
  - 재현: 정상 `queue-operation` 줄과 `Agent` 호출 줄 뒤에 바이트 `{"type":"x","k":"\xed\x95`(한글 3바이트 중 2바이트)로 끝나는 줄을 붙인 파일에 `agents`를 돌린다. 출력은 `세션 기록을 읽지 못했다: ... 'utf-8' codec can't decode bytes in position 0-1: unexpected end of data`, 종료 2다.
  - 근거: 이 도구의 핵심 쓰임은 압축된 뒤 살아 있는 지금 세션의 기록을 읽는 것이다. 그때는 마지막 줄이 쓰는 중일 수 있다. 독스트링은 이 동작을 "못 보는 것"에 적었지만, 잘린 마지막 줄은 깨진 JSON 줄로 세고 앞의 정상 줄은 살리는 쪽이 목적에 맞는다.
  - 제안: `encoding="utf-8", errors="replace"`로 열면 깨진 줄은 `json.loads`가 거르거나 `broken`으로 센다. 독스트링 항목과 그 시험을 같이 바꾼다.
- **[Minor] `tools/extract_asks.py:464`, `:428`, `:434`, `:470-473` — 한 줄로 찍는 칸(`description`(에이전트 설명), `header`, `option.label`, `run.name`, `agent_id`)에 줄바꿈이 있으면 출력 구조를 위조할 수 있다. 여러 줄 글은 `_block`이 네 칸 들여써 막지만 이 칸들은 거치지 않는다.**
  - 재현: 질문의 `header`를 `"H\n## 호출 9/9 질문 1/1"`로 하고 선택지 라벨을 `"B\n 7. fake"`로 한 호출을 `asks`로 돌린다. `머리: H` 다음 줄에 진짜 헤더처럼 보이는 `## 호출 9/9 질문 1/1`이 들어가고, 선택지 줄 아래 ` 7. fake`가 선택지처럼 찍힌다. 또 `Agent` 호출의 `description`에 `"x\n## 에이전트 9/9 · 가짜"`를 넣으면 가짜 에이전트 머리가 나온다.
  - 근거: 이 출력은 모델 세션이 읽는다. 값은 모델이 쓴 호출 입력이라 프롬프트 주입에 걸린 문서가 모델에게 시켜 만들 수 있다. 일지에 옮기기 전에 구조를 믿고 `--only`나 `grep`으로 가르는 사용을 속일 수 있다.
  - 제안: 한 줄 칸은 `repr`처럼 `\n`을 `\\n`으로 바꿔 찍거나 `_block`을 거치게 한다(`머리`, `라벨`, `설명 제목`, `이름`, `id`).
- **[Minor] `tools/extract_asks.py:371-377` — 한 `user` 줄에 `tool_result`가 둘 이상이면 줄 전체의 `toolUseResult.agentId`가 모든 결과에 붙는다.**
  - 재현: `Agent` 호출 둘(`t1`, `t2`)을 한 `assistant` 줄에 넣고, 뒤 `user` 줄에 `tool_result` 둘과 `"toolUseResult":{"agentId":"A1"}` 하나를 둔 뒤 `from="A1"` 보고 둘(같은 글)을 넣으면, 에이전트 1과 2가 모두 id `A1`이 되고 보고는 2에만 붙는다(1은 "보고가 기록에 없다").
  - 근거: `toolUseResult`는 줄 하나에 하나뿐이라 어느 결과의 것인지 알 수 없다. 이 저장소의 기록에서는 병렬 호출 결과가 줄마다 따로여서 아직 안 났을 수 있다. 확신은 낮고 `AskUserQuestion`에도 같은 모양(`collect_asks:312-319`)이 있다. 이 경우 답이 다른 호출에 붙으면 답 `answers`가 질문 글로 짝이 안 맞아 "이 질문의 답이 기록에 없다"가 된다.
  - 제안: 한 줄에 `tool_result`가 둘 이상이면 `toolUseResult`를 어느 쪽에도 붙이지 않고 "결과가 줄에 섞여 있다"고 적는다. 또는 "못 보는 것"에 적고 시험 하나로 고정한다.
- **[Minor] `tests/tools/test_extract_asks.py:648` (CodeRabbit 지적, 유효) — 한글 출력 시험이 `PYTHONUTF8`과 `PYTHONIOENCODING`을 환경에서 빼기만 하고 비 UTF-8 출력 조건을 강제하지 않는다.**
  - 근거: 리눅스 CI에서는 환경이 비어도 stdout이 UTF-8이라 `stream.reconfigure`를 지우는 변이(`extract_asks_mutations.toml:153`)가 CI에서 초록이 될 수 있다. 이 PC(윈도 파이프 cp949)에서만 빨강이 난다. `tests.md`의 "이 PC에서 초록인 것은 리눅스에서 돈다는 증거가 아니다"에 걸린다.
  - 제안: `env["PYTHONIOENCODING"] = "cp949"`와 `PYTHONUTF8` 제거로 비 UTF-8을 강제하고, `decode("utf-8")`로 읽는다. 변이가 어느 OS에서든 빨강이 된다.

### Nit
- **[Nit] `tools/extract_asks.py:523` — 기록 글을 그대로 찍어서 ESC, BEL 같은 제어 문자(`\x1b]0;…\x07` 등 터미널 제어)도 그대로 터미널에 나간다.** 기록에 웹 페이지나 에이전트 보고가 든다. 재현: 답 글에 `\u001b]0;pwn\u0007`를 넣고 터미널에서 돌리면 창 제목이 바뀐다. 이 도구는 주로 모델 세션이 파이프로 읽어 영향이 작다. `\n`·`\t` 외 C0 제어 문자를 `\x1b` 꼴로 바꿔 찍는 것을 제안한다. 위 Major의 `errors` 처리와 같은 자리에서 고치면 값이 싸다.
- **[Nit] `tools/extract_asks.py:387` — 같은 에이전트의 서로 다른 두 보고가 글이 같으면 하나로 합친다.** 이름 붙인 에이전트가 `SendMessage` 뒤에 "완료"만 두 번 보고하는 경우다. 독스트링의 "같은 보고가 되풀이돼도 한 번만"과 부딪히는 근본 한계이므로 "못 보는 것"에 한 줄 적으면 된다.
- **[Nit] `tools/extract_asks.py:208-225` (`_peel`) — 여러 개 고르기에서 직접 친 글이 `라벨, `로 시작하면 그 라벨을 고른 것으로 읽는다.** 예: 라벨 `A`가 있을 때 아무것도 안 고르고 `A, 그리고 더`를 친 경우다. 답 글에 경계가 없는 탓이라 고칠 수는 없고, 독스트링의 "직접 친 글이 앞에 오면" 항목에 이 반대 방향도 적으면 된다.
- **[Nit] `tools/extract_asks.py:159` — UTF-8 BOM으로 시작하는 파일은 첫 줄이 깨진 줄로 센다.** `utf-8-sig`로 열면 된다. 실제 기록에서는 본 적이 없다.

## 오탐 (고치지 않는다)
- 성능 우려 "기록 파일을 통째로 읽는 곳": 없다. `read_records`는 `for raw in handle`이고, 모든 `collect_*`는 리스트를 한 번 훑는다. `HANDBACK` 정규식도 줄 하나(보고 글 하나)에만 걸리고 `\A`로 닫혀 있어 폭주하지 않는다. 메모리는 위 Minor로만 본다.
- 보안 "기록의 지시를 따르거나 실행하는 길": 없다. `eval`, `exec`, `subprocess`, 파일 쓰기, 네트워크가 없고 읽기만 한다. 글은 문자열로만 다루고 출력에 찍는다. 모델이 출력의 지시를 따르는 것은 호출한 쪽의 몫이라 이 도구에서 막을 수 없다(구조 위조를 막는 것은 위 Minor).
- 보안 "인자로 받은 경로": 읽기 전용으로 열고 쓰지 않으며 `expanduser`만 한다. 디렉터리나 없는 파일은 `OSError`로 잡혀 종료 2다. `/dev/zero` 같은 장치 파일은 못 막지만 사용자가 직접 친 인자라 위협 모델 밖이다.
- 거짓 양성 후보 "답이 없는 질문": `no_result`, `answers`가 `None`인 질문 모두 "결과가 기록에 없다", "이 질문의 답이 기록에 없다"로 구분된다. 시험도 있다.
- 거짓 양성 후보 "직접 친 답과 고른 라벨": 단일 선택은 `text in labels`로, 목록 답은 라벨 일치 여부로 가르고, 라벨과 같은 글을 직접 친 것은 구분 불가한 근본 한계이며 입력 모양으로는 못 가른다.
- 거짓 양성 후보 "쉼표가 든 라벨": `_peel`이 긴 라벨 먼저로 벗기고 시험이 고정한다(`가, 나` 대 `가`).
- 거짓 양성 후보 "`--only 0`이나 음수": `not 1 <= only <= len`에 걸려 종료 1로 끝난다.
- ruff, pyright, 타입 우회, `FBT`, 시간대 같은 항목은 훅과 CI가 잡는 범위라 제외했다. `read_records`의 `Json` 재귀 별칭과 `type` 문은 pyright strict 범위다.

## 요약
- 총 10건: 유효 Major 1, Minor 5(그중 CodeRabbit 1건 포함), Nit 4. 오탐으로 접은 것은 위 일곱 항목이다. CLI 자체 지적은 1건이고 모두 유효(Minor)다. 유효 대 오탐은 CLI 1건 기준 1:0, 내 점검 기준 10:7이다.
- 좌석 상태: `Seat: not assigned`. 그래도 리뷰는 끝까지 돌았다(`review_completed`).
- 즉시 고칠 것: 서로게이트 출력 오류(`print`/`reconfigure`의 `errors`)와 잘린 UTF-8 줄 처리(`errors="replace"`)를 한 번에, 한 줄 칸의 줄바꿈 위조, 한글 시험의 cp949 강제.

받는 본 세션에게: 일지를 쓰는 세션이면 이 보고를 받은 이 턴에 일지로 옮긴다. 고친 것과 남긴 것은 지적마다 판정한 턴에 옮긴다(code-review 6단계 끝).

### 판정과 반영(PR 직전 리뷰)

**고친 것.**
- Major, 서로게이트 출력(`print`): 표준출력과 표준오류를 `errors="backslashreplace"`로 맞춰 짝 없는 `\ud800`을 글자 그대로 `\ud800` 꼴로 낸다. 종료 1이 "낼 것이 없다"와 섞이지 않는다. `main`에서 `UnicodeEncodeError`를 잡아 종료 2로 끝내자는 제안은 따르지 않았다. 출력이 깨지지 않으니 잡을 일이 없다. 시험(`test_짝_없는_서로게이트_문자가_든_글도…`, 스크립트를 부르고 표준출력을 cp949로 강제)과 변이 하나를 더했다.
- Minor, 잘린 UTF-8 줄: 파일을 `errors="replace"`로 연다. 한글 중간에서 잘린 마지막 줄은 JSON으로 읽히지 않아 읽지 못한 줄로 세고, 앞의 줄은 읽는다. 독스트링의 "못 보는 것" 항목을 새 동작으로 바꿨고, 종료 2로 끝난다던 옛 시험은 새 시험으로 바꿨다. `main`의 `except`에서 `UnicodeDecodeError`를 뺐다.
- Minor, 메모리: `read_records`가 `assistant`, `user`, `queue-operation`, `attachment`가 아닌 줄(`api-request-blob` 등)을 읽자마자 버린다. 생성기로 바꾸자는 제안은 따르지 않았다. 호출하는 쪽(`collect_*`)이 목록을 여러 번 훑지는 않지만 `Numbered` 모양을 시험 전체가 쓰고, 거르는 것만으로 재현에서 가장 큰 몫(큰 읽기 결과와 `api-request-blob`)이 빠진다. 시험과 변이를 더했다.
- Minor, 한 줄 칸의 줄바꿈: 머리, 선택지 라벨, 에이전트 설명, 이름, id, 시각을 `one_line`을 거쳐 `\n` 두 글자로 낸다. 가짜 `## 호출`, ` 7.`, `## 에이전트` 줄이 안 생기는지 시험과 변이로 고정했다.
- Minor, 한 줄에 `tool_result`가 둘 이상: 그 줄의 `toolUseResult`를 어느 쪽에도 붙이지 않는다(`_line_result`). 질문은 구조 없는 결과로, 에이전트는 id 없이 나온다. 실제 기록에서는 본 적이 없지만(결과가 줄마다 따로다) 독스트링의 "못 보는 것"에 적고 시험 둘과 변이 둘을 더했다(러너가 첫 실패에서 멈추므로 시험마다 변이를 따로 둔다).
- Minor, 한글 시험의 cp949 강제(CodeRabbit): `PYTHONIOENCODING=cp949`를 걸고 `PYTHONUTF8`을 뺀다. 리눅스에서도 `reconfigure`를 지운 변이가 빨강이 된다.
- Nit, BOM: `utf-8-sig`로 연다. 시험과 변이를 더했다.
- Nit, 같은 글의 두 보고와 `라벨, 글`로 시작하는 직접 친 글: 둘 다 근본 한계라 독스트링에 적고, 뒤의 것은 시험 하나로 고정했다(앞의 것은 되풀이 걷기 시험이 이미 그 입력이다).

**남긴 것.**
- Nit, 터미널 제어 문자(ESC 등): 걸러 내지 않고 독스트링의 "못 보는 것"에 적었다. 이 도구의 출력은 주로 모델 세션이 파이프로 읽고, 걸러 내면 일지에 글자 그대로 옮긴다는 약속과 부딪힌다. 사람이 터미널에서 직접 읽다 창 제목이 바뀌는 정도라 막는 값이 작다고 보았다. 못 보는 것 항목은 시험 하나(`test_터미널_제어_문자도_걸러_내지_않고_그대로_낸다`)로 고정했다(걸러 내는 쪽으로 바뀌면 이 시험이 빨강이 된다).
- 오탐 일곱은 보고의 판정을 그대로 따랐다.

**다시 돌린 명령과 결과.**
- `uv run pytest -q -p no:cacheprovider -n 0 tests/tools/test_extract_asks.py`: 48개 통과.
- `uv run ruff format`과 `uv run ruff check`(두 파일): 바꿀 것 없음, 통과. `uv run pyright`(두 파일): 오류 0.
- `uv run python -X utf8 tools/mutate.py .scratch/harness/probes/extract_asks_mutations.toml --check`: 변이 20개 모두 원문이 한 번씩 있다.
- `PYTHONUTF8=1 uv run python tools/mutate.py .scratch/harness/probes/extract_asks_mutations.toml`: 기준선 20개 초록, 변이 20개 모두 기대대로 빨강. 커밋하지 않은 변경이 있다는 알림(막지 않는다)이 떴고, 이 실행은 PR 직전 리뷰를 반영한 뒤의 확인이다. 전체 실행은 커밋 뒤에 한 번 더 돈다.
- 나머지 검증 명령(전체 `pytest`, `lint-imports`, 하네스 검사)은 커밋이 부르는 pre-commit의 결과로 갈음한다. 결과는 커밋 뒤 이 일지와 PR 본문에 적는다.
