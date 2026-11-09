"""UserPromptSubmit 훅. 첫 메시지가 next-session 지시문이면 새 세션이 스스로 이름을 붙이게 하고,
지시문이 아니면 티켓·브랜치·제목의 차례를 알린다(아래 "첫 턴 티켓 알림").

이름은 여는 쪽(open-session 4단계)이 붙였는데, 첫 줄이 슬래시 명령이면 앱이 딥링크의 `/` 를 전각
`／`(U+FF0F)로 바꿔 넣어 여는 쪽이 `held=` 에서 멈추고, 사람은 새 세션에서 고쳐 보낸 뒤 옛 세션으로
돌아오지 않았다. 티켓 03·05 세션이 앱이 지은 제목으로 남았다. 그래서 받는 쪽이 붙인다. 훅은 MCP
도구를 부를 수 없으니 계기만 넣는다(CLAUDE.md 교정 루프). 형식의 원천은 next-session 스킬이다.

사람이 `／` 를 고치지 않고 보내면 스킬이 로드되지 않는다(티켓 05 세션 실측). 그때는 스킬 파일을
읽어 따르라는 줄을 붙인다. 앱의 전각 치환은 출처 모를 링크가 명령을 일으키지 못하게 하는 장치인데,
여기까지 온 것은 사람이 보내기를 누른 뒤라 그 확인은 이미 있었다. open-session 은 이제 쏘기 전에 이
저장소의 스킬 명령을 같은 뜻의 한 줄로 옮겨 사람 손 없이 보낸다(2026-09-24, `open_session.ps1` 의
`Convert-StartLine`). 그래서 이 경로에 오는 것은 `held=` 로 멈춘 화면을 고치지 않고 보낸
경우인데, 이제 `held=` 는 스킬 파일이 없을 때만 나므로 그때 가리키는 파일도 없다. 실제로 이 경로를
쓰는 것은 그 변경 전에 열린 화면이다. 손으로 붙여 넣은 지시문의 `/` 는 반각이라 진짜 명령이 되어
여기 오지 않는다.

첫 턴에만 낸다. 내용만으로는 "지시문으로 연 세션"과 "지시문을 붙여 넣고 이야기하는 세션"이 같다.
이 훅을 만든 세션에 사람이 지시문을 붙여 질문하자 훅이 그 세션 이름을 바꾸라고 했고, 제목이 앱이
지은 것이라 따랐으면 묻지 않고 바뀌었다(실측). 같은 제목이 둘이 되면 open-session 1단계가 "그
세션이 하고 있다"며 열지 않는다. 지시문으로 연 세션은 지시문이 언제나 첫 메시지이므로,
트랜스크립트에 assistant 기록이 아직 없을 때만 낸다. 훅이 도는 시점에 지금 프롬프트가 기록됐는지와
무관하다.

못 보는 것: 지시문 모양은 누구나 쓸 수 있다. 막는 것은 첫 턴이라는 것, 이름이 kebab 한 토막이라
`.claude/skills/` 밖을 가리키지 못한다는 것, open-session 이 옮긴 첫 줄이면 연 저장소와 작업 폴더가
같다는 것, 옮긴 첫 줄의 머리인데 표지를 못 읽으면 막는다는 것뿐이다. 보내기는 이제 사람이 아니라
open-session 스크립트가 하기도 한다. 이 폴더 가드는 새 훅이 도는 폴더에서만 선다. 이 변경 전
브랜치의 워크트리는 옛 훅을 쓰고, 그때 남는 것은 첫 줄의 조건 문장과 상대 경로다(저장소가 아닌
폴더에서는 파일을 못 찾는다). 사람이 손으로 연 새 세션에 지시문을 첫 메시지로 붙여 넣은 것도
발동하는데, 그것은 open-session 이 하는 일과 같아 의도한 쪽이다. `/clear` 뒤의 첫 메시지도 같다.
트랜스크립트가 새 파일로 시작해 assistant 기록이 없으므로 발동하고, 같은 앱 세션이 그 지시문의 일로
새로 시작하는 것이라 이름을 바꾸는 것이 맞다고 본다.

`self` 는 데스크톱 앱의 세션 도구가 받는다. claude.ai 클라우드 세션의 `set_session_title` 은 `self`
를 거부했고 세션 ID 로는 바뀌었다(대기열 81, 일지 2026-10-01-05). 그 세션이 ID 를 어디서 얻었는지는
기록에 없어, 계기 문구는 길을 정하지 않고 ID 를 넘기라고 한다. 실행할 수 없는 지시만 남지 않게,
찾지 못하면 제목을 두고 사용자에게 알리게 한다. 막다른 길은 적는다. 데스크톱 앱의
`list_sessions` 는 이 세션을 빼고(도구 설명, open-session 4단계), `get_session` 은 이 세션을 `self`
로만 가리킨다. 훅 입력의 Claude Code 세션 ID 도 앱의 세션 ID 가 아니다 — 데스크톱에서 트랜스크립트
파일 이름(`59aeea28-…`)과 `get_session self` 의 `local_0ca607c2-…` 가 달랐다(2026-10-01 손으로
봤다). 못 보는 것: 클라우드 세션에서 이 세션의 ID 를 얻는 길. 재지 않았다.

주 체크아웃 미갱신. 워크트리에서 병합한 세션은 앱의 워크트리 가드 때문에 주 체크아웃을 당기지
못해, 지시문의 '확인할 선행 조건'에 미갱신 한 줄을 남기고 묶음의 첫 지시문이면 '어디서' 줄의
워크트리 문장을 `tidy-checkouts` 로 시작한다(next-session `directive.md` 가 원천이고 순서와 첫
세션만인 이유도 거기 있다). 계기는 그 순서(제목, `tidy-checkouts`, 워크트리 문장)와 첫 세션만이라는
것을 다시 짚는다. 판정은 그 스킬에 그대로 맡기고, 사람에게 넘기는 확인을 기다리면 첫 턴이 멈추므로
잇게 한다. 훅이 셸에서 git 으로 대신 당기지 않는 것은 그것이 가드를 돌아가는 길이라서다. 못 보는 것:
미갱신 줄이 생길 때 주 체크아웃은 정의상 낡았고 새 세션의 훅은 그 사본이다. 이 계기를 들인 병합
뒤 주 체크아웃이 한 번 당겨지기 전에는 옛 훅이 돌고, 옛 훅은 워크트리 문장을 다른 일보다 먼저
따르라고만 한다. 그래서 순서는 그 문장 안에 있다. 작업 폴더가 주 체크아웃인지는 이 계기가 보지
않는다 — open-session 이 옮긴 첫 줄이면 위의 폴더 가드가, 아니면 `tidy-checkouts` 1이 본다.

손으로 연 세션(대기열 72). open-session 이 새 세션을 열지 못하면 사람이 손으로 열어 지시문을
붙여 넣는다. 그 일은 앞 세션의 일지가 병합된 뒤에 나서 그 일지에 적힐 자리가 없었고, 09-29
12:28 부터 09-30 17:04 까지 열한 번(두 번째 인스턴스 기록으로 센 수)이 그동안 한 번도 세어지지
않았다(뒤에 일지 2026-09-30-06 이 셌다). 그래서 받는 쪽이 붙여 넣은 꼴을 알아보면 이 세션의 일지에
그 사실을 바로 적으라는 계기를 더한다. 계기는 첫 턴에만 오고 일지는 보통 단계를 닫을 때 쓰므로,
미루면 컨텍스트 압축이나 끊김에 그 한 줄이 사라진다(셀프 리뷰 두 축). 꼴의 판정은 `pasted_reason`
이다. 못 보는 것: 사람이 슬래시 명령이 아닌 시작 프롬프트를 첫 줄에 쳐 넣고 지시문을 붙이면
open-session 이 보낸 글과 같아 가르지 못한다(하네스 chore 의 시작 프롬프트가 그 꼴이다). 첫 줄을
옮기는 쪽은 여는 쪽이 넘긴 루트의 스킬 파일을, 이 판정은 이 세션의 작업 폴더의 스킬 파일을 본다. 그
스킬이 한쪽에만 있으면 틀린다(작업 폴더에만 있으면 `held=` 뒤 고쳐 보낸 글을 붙여 넣은 것으로 본다).

첫 턴 티켓 알림(agent-os ADR 0037 과 그 저장소의 `.scratch/ticket-for-every-pr/spec.md` 의 "첫 턴
알림"에서 옮겼다. rag-engine 규약의 원천은 `docs/agents/issue-tracker.md`). 첫 메시지가
지시문이 아니면 사람이 손으로 열었거나 사람이 시킨 카드로 열린 세션이다. 그 세션에는 지시문의
브랜치 줄이 없어, 티켓 없이 커밋하다 커밋 검사(`tools/check_ticket.py`)에 막힌다. 그래서 첫 턴에 한
번 티켓·브랜치·제목의 차례와 따르지 않는 때를 알린다(`TICKET_NOTICE`). 넷이 모두 맞을 때 낸다.
첫 턴이고, 첫 메시지가 지시문이 아니고, 사람이 보는 세션이고, 첫 메시지가 `<scheduled-task ` 로
시작하지 않는다. 헤드리스 가름(`is_attended`)은 agent-os 의 `tools/hook_session_usage.py` 의
`shows_summary` 에서 옮겼다(그 훅과 카나리아는 rag-engine 에 복사하지 않았다). agent-os 에서는
카나리아가 새 세션에서 스킬을 불러 보는 동안 이 알림이 끼어들지 않게 하려는 것이었다. 앱의 예약
작업이 연 세션은 그 가름으로 헤드리스로 보이지 않아(2026-10-21 `daily-morning-report` 세션이 사용량
요약을 받았다, 명세의 검토 주석) 첫 메시지의 머리로 거른다. 그 검토가 본, 첫 메시지가 그 머리인 세션
여덟은 모두 저장소를 고치지 않는 일이었고(아침 보고는 `tools/morning_tasks/common.md` 가 "저장소의
파일을 고치거나 커밋하지 않는다"고 적는다), 알림이 할 일을 바꾸지 않는 세션에는 싣지 않는다.
지시문에는 이 알림을 내지 않는다. 지시문은 티켓 모양이나 `docs/` 브랜치를 주고, 지시문의 계기(제목,
`tidy-checkouts`, 폴더 막기)는 헤드리스 가름을 보지 않고 전과 같다. 제목
문구는 두 계기가 같이 쓴다(`TITLE_CALL`, `TITLE_FALLBACK`). 주 체크아웃에서 시작했는지와 지금
브랜치가 다른 티켓의 것인지는 훅이 가르지 않고 조건 문장으로 두어, 모델이 작업 폴더와 브랜치를 보고
가른다. 둘 다 티켓을 쓰기 전에 본다.

비용. 이제 지시문이 아닌 프롬프트에서도 트랜스크립트를 연다. `has_assistant_turn` 은 첫 assistant
기록에서 멈추고, 첫 턴이 지난 트랜스크립트에서 그 기록은 앞쪽에 있다. 헤드리스 가름과 예약 작업
거르기를 트랜스크립트보다 먼저 본다. 잰 시간은 `.claude/rules/tools.md` 의 훅별 시간이다.

못 보는 것. 첫 메시지만으로는 질문만 하는 세션과 커밋할 세션을 가르지 못해 질문에도 알린다(알림이
따르지 않는 때로 든다). 커밋하지 않는 스킬의 슬래시 명령(`/tidy-checkouts`)으로 연 세션도 첫
메시지가 지시문이 아니라 알린다. 첫 assistant 기록이 쓰이기 전에 둘째 프롬프트가 들어오면 그
프롬프트에도 알리는지는 보지 않았다(지시문 계기도 같다). 지시문 모양의 글을 붙여 넣고 다른 일을
시키면 지시문으로 보아 이 알림이 뜨지 않는다. `/clear` 뒤의 첫 메시지는 트랜스크립트가 새 파일이라
새 세션과 같은 입력이고 다시 알린다(이미 티켓과 브랜치가 있는 일을 잇는 것이면 그대로 두라는 줄이
받는다). 예약 작업이 연 세션의 훅 입력 `prompt` 가 트랜스크립트의 첫 메시지와 같은 머리로 시작한다는
것은 재지 않았다(트랜스크립트만 읽었다). `daily-morning-report` 밖의 예약 작업이 헤드리스로
보이는지는 보지 못했다. 예약 작업이 커밋할 일을 맡게 되면 이 알림 없이 커밋 검사가 처음 알린다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

FULLWIDTH_SLASH = "／"
_BRANCH_LINE = "브랜치:"
_NEW_SESSION = re.compile(r"어디서:\s*새 세션")
# 스킬 이름. 곧 경로라 kebab 한 토막만 받는다.
_KEBAB = r"[a-z0-9][a-z0-9-]*"
_SKILL_NAME = re.compile(rf"({_KEBAB})(?:\s|$)")
# open_session.ps1 의 Convert-StartLine 이 옮긴 첫 줄의 고정 머리. 표지 줄과 머리 판정이 이 하나를
# 같이 쓴다. 머리는 맞는데 표지를 못 읽을 때 막는 이유와 못 보는 것은 `block_reason_for` 독스트링.
_OPENED_HEAD_PATTERN = rf"\.claude/skills/{_KEBAB}/SKILL\.md 를 읽어 그대로 따른다\."
_OPENED_HEAD = re.compile(_OPENED_HEAD_PATTERN)
# 옮긴 첫 줄 전체. 머리 뒤에 연 저장소를 표지로 든다. 문구의 원천은 그 스크립트다.
_OPENED_LINE = re.compile(_OPENED_HEAD_PATTERN + r" 이 세션을 연 저장소는 `(?P<root>[^`]+)`이고")
# "어디서" 줄의 워크트리 문장(next-session `directive.md`). 받는 쪽은 지시문 자체라 첫 턴 계기가
# 짚는다.
_WHERE_LABEL = "어디서:"
# 워크트리에서 병합한 세션이 주 체크아웃을 당기지 못했다는 줄(next-session `merge.md` "워크트리에서
# 병합할 때" 4)과 그 줄이 사는 라벨, "어디서" 줄의 묶음 표시(next-session `directive.md`). 문구의
# 원천은 그 스킬이고
# tests/tools 의 계약 테스트가 대조한다. 미갱신은 콜론까지 대조해 같은 줄의 부정이나 설명("미갱신
# 아님")을 세지 않는다. 묶음 표시의 그룹은 k 하나다.
_CONDITION_LABEL = "확인할 선행 조건:"
_STALE_ROOT = "주 체크아웃 미갱신:"
_BUNDLE = re.compile(r"나란히 여는\s*\d+\s*중\s*(\d+)")
# 미갱신 지시문에 붙는 계기. 묶음의 첫 세션(묶음이 아니면 그 세션)과 나머지 세션.
_TIDY_FIRST = (
    " 지시문의 '확인할 선행 조건'이 주 체크아웃 미갱신을 말한다. 제목을 바꾼 뒤 워크트리에 "
    "들어가기 전에 Skill 도구로 `tidy-checkouts` 를 돈다. 그 스킬은 주 체크아웃 세션에서만 "
    "루트를 당기고, 워크트리에 들어간 뒤나 주 체크아웃이 아닌 폴더에서는 1에서 멈춘다. 무엇을 "
    "당기고 지울지는 그 스킬이 정한다. 그 스킬이 멈추거나 사람에게 넘기는 것은 보고만 하고 답을 "
    "기다리지 않고 지시문을 잇는다."
)
_TIDY_LATER = (
    " 지시문의 '확인할 선행 조건'이 주 체크아웃 미갱신을 말하지만, 이 세션은 나란히 여는 묶음의 "
    "첫 세션이 아니라 `tidy-checkouts` 를 돌지 않는다 — 첫 세션이 돈다. 함께 돌면 같은 루트를 "
    "함께 당기거나 같은 워크트리를 함께 지우려 할 수 있다."
)
# next-session `directive.md` 형식 블록의 라벨. 첫 줄이 이 가운데 하나로 시작하면 시작 프롬프트 줄
# 없이 지시문만 붙여 넣은 것이다(대기열 72). tests/tools 의 계약 테스트가 그 블록과 대조한다.
_DIRECTIVE_LABELS = (
    "다음 작업:",
    "다음 단계:",
    "어디서:",
    "시작 프롬프트:",
    "브랜치:",
    "모델:",
    "읽을 것:",
    "이어받을 상태:",
    "확인할 선행 조건:",
    "이번 요청 범위:",
)


# 헤드리스 가름의 두 변수. agent-os 의 `tools/hook_session_usage.py` 의 `shows_summary` 에서 옮겼다.
# 뒤의 것은 agent-os 카나리아의 표지 이름 그대로다. rag-engine 에는 그 변수를 붙이는 도구가 없고,
# 훅 러너(`tools/run_hooks.py`)가 자식 환경에서 벗긴다.
ATTENDED_VAR = "CLAUDE_CODE_SESSION_ATTENDED"
HEADLESS_MARKER = "AGENT_OS_HEADLESS"
# 제목을 바꾸라는 두 계기(지시문, 티켓 알림)가 같이 쓰는 문장. 도구를 부르는 꼴 뒤에 브랜치가 온다.
TITLE_CALL = "`set_session_title` 에 `self` 와"
TITLE_FALLBACK = (
    "앱이 지은 제목이면 묻지 않고 바뀐다. 도구가 `self` 를 거부하면(클라우드 세션에서 그랬다) 이 "
    "세션의 ID 를 찾아 `self` 대신 넘기고, 찾지 못하면 제목을 바꾸지 않고 사용자에게 알린다. "
    "데스크톱 앱의 세션 도구로는 찾지 못한다 — `list_sessions` 는 이 세션을 빼고 `get_session` 은 "
    "이 세션을 `self` 로만 가리킨다."
)
# 앱의 예약 작업이 연 세션의 첫 메시지 머리. 그 세션에는 티켓 알림을 내지 않는다.
_SCHEDULED_TASK = "<scheduled-task "
# 지시문이 아닌 첫 메시지에 붙는 알림. 차례의 원천은 `docs/agents/issue-tracker.md` 다(알림은
# agent-os ADR 0037 에서 옮겼다).
TICKET_NOTICE = (
    "지시문 없이 연 세션의 첫 메시지다. 이 일이 커밋할 일이면 코드를 고치기 전에 티켓, 브랜치, "
    "세션 제목을 차례로 맞춘다. 이 세션이 주 체크아웃에서 시작했으면 그보다 먼저, 주 "
    "체크아웃에서 브랜치를 따지 않고 `EnterWorktree` 로 워크트리에 들어간다 — 주 체크아웃에 먼저 "
    "쓴 티켓은 새 워크트리에 따라오지 않고, 추적하지 않는 파일로 남아 그 경로를 병합한 main 을 "
    "당기지 못하게 한다. 지금 브랜치가 이 일이 아닌 다른 티켓의 브랜치(`feature/<NN>-<slug>`, "
    "`chore/<slug>` 모양의 다른 이름)면 그 브랜치와 워크트리는 그 티켓의 것이라, 아래 셋을 "
    "하지 않고 사용자에게 알린다 — 거기 쓴 새 티켓과 바꾼 이름은 남의 PR 에 섞인다. "
    "1) 티켓을 쓴다. 받은 일의 티켓 파일이 이미 있으면 새로 쓰지 않고, 상태가 "
    "`ready-for-agent` 면 `in-progress` 로 바꾼다. 기능 폴더의 일(끝난 기능의 동작을 고치는 제품 "
    "코드는 그 동작을 만든 기능 폴더다)이면 `.scratch/<slug>/issues/` 의 다음 두 자리 번호이고, "
    "하네스 일이나 기능에 들지 않는 작은 문서 고침이면 `.scratch/harness/issues/<slug>.md` "
    "이며 그 <slug> 는 번호 없이 영어 소문자로 시작하는 이름을 직접 짓는다. "
    "상태는 `in-progress` 이다. "
    "2) 브랜치를 티켓 자리에 맞춘다. 이름은 티켓 파일 이름의 stem 이라(`feature/<NN>-<slug>`, "
    "`chore/<slug>`), 워크트리에 들어오며 생긴 브랜치나 앱이 만든 `claude/<이름>` 브랜치를 "
    "`git branch -m <새 이름>` 으로 바꾼다. "
    f"3) 세션 제목을 그 브랜치로 바꾼다 — {TITLE_CALL} 그 브랜치. " + TITLE_FALLBACK + " "
    "따르지 않는 때는 셋이다. 커밋할 일이 없으면(질문, 읽기) 따르지 않는다. 면제 일(설계·명세·티켓 "
    "쓰기, 일지·대기열만 바꾸기)이면 1) 없이 `docs/<slug>` 브랜치로 하고, 워크트리와 제목은 위와 "
    "같다(그 PR 에서 회고가 고침을 반영할 때 쓰는 harness 티켓은 `retro` 가 정한다). 이미 티켓과 "
    "브랜치가 있는 일을 잇는 것이면(인계, 끊은 뒤 이어 가기, 열린 PR 반영) 그대로 둔다. "
    "커밋 검사(`tools/check_ticket.py`)가 티켓 없는 브랜치의 커밋을 막는다. 규약의 원천은 "
    "`docs/agents/issue-tracker.md` 다."
)


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    prompt: str
    transcript_path: str
    cwd: str


class TranscriptRecord(TypedDict, total=False):
    """트랜스크립트 JSONL 한 줄 중 이 훅이 읽는 부분."""

    type: str


def context_for(prompt: str, cwd: str | None = None) -> str | None:
    """새 세션 지시문이면 계기 문장, 아니면 None.

    지시문은 줄 머리에 `브랜치:` 줄(값이 있다)과 `어디서: 새 세션` 줄이 있는 프롬프트다. 문장 속에서
    형식을 인용한 것은 세지 않는다. `cwd` 는 이 세션의 작업 폴더로, 손으로 붙여 넣은 반각 슬래시
    명령을 가를 때 스킬 파일을 찾는 자리다(`pasted_reason`).
    """
    branch = directive_branch(prompt)
    if branch is None:
        return None
    context = (
        "next-session 지시문으로 연 새 세션이다. 여는 쪽은 이름을 붙이지 않는다. 다른 일보다 먼저 "
        f"이 세션의 제목을 지시문의 브랜치 이름으로 바꾼다 — {TITLE_CALL} `{branch}`. "
        + TITLE_FALLBACK
    )
    stale = _stale_root(prompt)
    tidies = stale and _first_of_bundle(prompt)
    if stale:
        context += _TIDY_FIRST if tidies else _TIDY_LATER
    if _wants_worktree(prompt):
        after = "`tidy-checkouts` 를 돈 뒤" if tidies else "제목을 바꾼 뒤"
        context += (
            f" 지시문의 '어디서' 줄이 워크트리를 말한다. {after} 다른 일보다 먼저 그 "
            "문장을 따른다. 주 체크아웃에서 새 브랜치를 따지 않는다 — 그 체크아웃은 다른 세션이 "
            "쓰고 있을 수 있다."
        )
    skill = _fullwidth_skill(prompt)
    if skill is not None:
        context += (
            f" 첫 줄의 슬래시 명령이 전각 `{FULLWIDTH_SLASH}`(U+FF0F)라 스킬이 로드되지 않았다. "
            f"`.claude/skills/{skill}/SKILL.md` 를 읽어 그대로 따른다. "
            "스킬의 인자는 첫 줄의 이름 뒤부터 메시지 끝까지다."
        )
    pasted = pasted_reason(prompt, cwd)
    if pasted is not None:
        context += (
            f" 이 지시문은 open-session 이 보낸 꼴이 아니다. {pasted}. open-session 은 시작 "
            "프롬프트를 첫 줄에 두고, 이 저장소의 스킬 명령이면 스킬 파일을 읽으라는 문장으로 "
            "옮겨 보낸다. 그래서 이 세션은 사람이 손으로 열어 붙여 넣은 것이고, 앞 세션의 "
            "open-session 이 이 세션을 열지 못했거나 쓰이지 않았다. 그 일은 앞 세션의 일지가 "
            "병합된 뒤에 나서 거기 적힐 자리가 없으므로, 이 세션의 일지에 그 사실을 한 줄 "
            "적는다(대기열 72). 이 계기는 첫 턴에만 오니 미루지 않는다. 위의 제목·워크트리 "
            "계기를 따른 뒤 일지 파일이 아직 없으면 `docs/journal/<날짜>-<HHMM>-<슬러그>.md` 를 "
            "머리 한 줄 파일로 만들고(앞부분은 Bash 의 `date +%Y-%m-%d-%H%M` 이나 PowerShell 의 "
            "`Get-Date -Format yyyy-MM-dd-HHmm`) 그 한 줄을 바로 적는다. 까닭을 모르면 "
            "모른다고 적는다."
        )
    return context


def first_turn_context(
    prompt: str,
    cwd: str | None,
    transcript_path: str | None,
    attended: str | None,
    marker: str | None,
) -> str | None:
    """첫 턴에 붙일 계기. 지시문이면 지시문 계기, 아니면 티켓 알림이고 첫 턴이 아니면 None.

    티켓 알림은 사람이 보는 세션이고(`is_attended`) 첫 메시지가 앱의 예약 작업이 아닐 때만 낸다. 그
    둘을 트랜스크립트보다 먼저 본다. 지시문 계기는 이 둘을 보지 않는다.
    """
    context = context_for(prompt, cwd)
    if context is None:
        if not is_attended(attended, marker) or prompt.lstrip().startswith(_SCHEDULED_TASK):
            return None
        context = TICKET_NOTICE
    if not is_first_turn(transcript_path):
        return None
    return context


def is_attended(attended: str | None, marker: str | None) -> bool:
    """사람이 보는 세션인지. `CLAUDE_CODE_SESSION_ATTENDED` 가 `0` 이거나 표지가 있으면
    헤드리스다."""
    return attended != "0" and not marker


def pasted_reason(prompt: str, cwd: str | None) -> str | None:
    """open-session 이 보낸 꼴이 아니라 사람이 붙여 넣은 지시문이면 그렇게 본 까닭, 아니면 None.

    open-session 은 시작 프롬프트를 첫 줄에 두고(그 스킬 2단계), 첫 줄이 이 저장소의 스킬 명령이면
    스킬 파일 문장으로 옮겨 보낸다(`Convert-StartLine`). 그래서 둘을 손으로 붙여 넣은 꼴로 본다.
    첫 줄이 지시문의 라벨 줄이다(시작 프롬프트 줄이 없다). 첫 줄이 반각 `/<스킬>` 이고 작업 폴더에
    그 스킬 파일이 있다(옮겨졌어야 했다). 반각 `/` 는 진짜 명령이 되어도 훅이 원문을
    받는다(`.scratch/harness/probes/slash_prompt_payload/probe.py`, claude 2.1.300 의 `claude -p`.
    데스크톱 앱의 입력창에 붙여 넣은 길은 재지 않았다). 스킬 파일이
    없는 반각 명령은 open-session 이 `held=` 로 멈춘 뒤 사람이 `／` 를 고쳐 보낸 글과 같아 세지
    않는다. 작업 폴더를 모르면 그 파일을 볼 수 없어 세지 않는다.
    """
    head = prompt.lstrip()
    first = head.splitlines()[0].strip() if head else ""
    for label in _DIRECTIVE_LABELS:
        if first.startswith(label):
            return f"첫 줄이 시작 프롬프트가 아니라 지시문의 `{label}` 줄이다"
    if not cwd or not head.startswith("/"):
        return None
    match = _SKILL_NAME.match(head, 1)
    if match is None:
        return None
    skill = match.group(1)
    if not (Path(cwd) / ".claude" / "skills" / skill / "SKILL.md").is_file():
        return None
    return f"첫 줄이 반각 `/{skill}` 이고 작업 폴더에 `.claude/skills/{skill}/SKILL.md` 가 있다"


def block_reason_for(prompt: str, cwd: str | None) -> str | None:
    """open-session 이 옮긴 지시문인데 작업 폴더가 연 저장소와 다르면 프롬프트를 막을 이유.

    딥링크는 폴더를 싣지 않고 앱이 마지막 폴더를 쓴다. 그것이 워크트리면 거기에도 같은 스킬 파일이
    있어, 자동 제출된 세션이 사람이 폴더를 보던 눈 없이 엉뚱한 곳에서 시작한다(PR #65 의
    CodeRabbit).
    모델에게 권하지 않고 막는다. 첫 줄이 "그대로 따른다"라고 말하므로 권고는 그것과 다툰다. 막으면
    이름도 붙지 않는다 — 붙으면 다음 open-session 이 그 제목을 살아 있다고 보고 열지 않는다. 작업
    폴더를 모르면(없거나 빈 값) 막는다.

    첫 줄이 ps1 의 고정 머리(`<스킬 경로> 를 읽어 그대로 따른다.`)로 시작하는데 표지를 읽지 못해도
    막는다(fail-closed). 쏘는 ps1 은 여는 세션의 작업 폴더 사본이고 이 훅은 받는 세션의
    `${CLAUDE_PROJECT_DIR}` 사본이라, 여는 세션이 워크트리면 둘이 다른 브랜치의 것일 수 있다.
    문구가 갈렸을 때 지나가면 폴더 가드가 조용히 꺼진다(2026-10-05 워크트리 감사 13). 사람이 스킬
    경로로 시작해 쓴 첫 줄은 그 머리가 아니라 막지 않는다. 머리까지 바뀌면 지나간다 — 한 체크아웃
    안에서는 tests/tools 의 계약 테스트가 잡지만, 두 체크아웃 사이의 머리 변경은 못 잡는다. 버린
    길: ps1 을 절대 경로로 불러 한 체크아웃에 묶으면 워크트리에서 ps1 을 고쳐 시험할 수 없게 된다.
    """
    if directive_branch(prompt) is None:
        return None
    head = prompt.lstrip()
    match = _OPENED_LINE.match(head)
    if match is None:
        if _OPENED_HEAD.match(head) is None:
            return None
        return (
            "첫 줄이 스킬 파일을 가리키는데 연 저장소 표지를 읽지 못했다. 이 지시문을 쏜 "
            "`tools/open_session.ps1` 과 이 훅이 다른 체크아웃의 사본이라 문구가 갈렸을 수 "
            "있다. 작업 폴더를 확인할 수 없어 이 프롬프트를 막았다. 두 체크아웃의 사본을 맞춘 "
            "뒤 다시 연다."
        )
    root = match.group("root")
    if cwd and _folder_key(root) == _folder_key(cwd):
        return None
    return (
        f"이 세션의 작업 폴더 `{cwd or '(알 수 없음)'}` 가 지시문을 연 저장소 `{root}` 와 다르다. "
        "스킬을 따르지 않도록 이 프롬프트를 막았다. 연 저장소에서 세션을 다시 연다."
    )


def _labeled_lines(prompt: str, label: str) -> list[str]:
    """줄 머리가 `label` 인 줄들. 앞뒤 공백을 벗긴다. 문장 속에서 라벨을 인용한 것은 세지 않는다."""
    stripped = (line.strip() for line in prompt.splitlines())
    return [line for line in stripped if line.startswith(label)]


def _wants_worktree(prompt: str) -> bool:
    """줄 머리의 `어디서:` 줄에 `EnterWorktree` 가 들었는가."""
    return any("EnterWorktree" in line for line in _labeled_lines(prompt, _WHERE_LABEL))


def _stale_root(prompt: str) -> bool:
    """줄 머리의 `확인할 선행 조건:` 줄에 주 체크아웃 미갱신이 들었는가."""
    return any(_STALE_ROOT in line for line in _labeled_lines(prompt, _CONDITION_LABEL))


def _first_of_bundle(prompt: str) -> bool:
    """묶음이 아니거나 묶음의 첫 세션인가. `어디서:` 줄의 `나란히 여는 <N> 중 <k>` 를 본다.

    k 가 글자 그대로 1일 때만 첫 세션이다. 0 이나 `01` 처럼 잘못 적은 수도 첫 세션이 아니라고
    본다 — 돌지 않으면 루트가 낡은 채 남을 뿐이고, 함께 돌면 같은 루트나 워크트리를 다툴 수 있다.
    """
    for line in _labeled_lines(prompt, _WHERE_LABEL):
        match = _BUNDLE.search(line)
        if match is not None:
            return match.group(1) == "1"
    return True


def directive_branch(prompt: str) -> str | None:
    """새 세션 지시문이면 `브랜치:` 줄의 값, 아니면 None.

    공개 이름인 것은 다시 풀기 러너(`tools/rerun_continue.py`)가 세션의 결과 글에서 인계 지시문을
    알아보는 데 이 함수를 import 하기 때문이다. 받는 쪽(이 훅)과 러너가 같은 판정으로 지시문을
    알아본다. 훅은 단독 실행이라 이 모듈이 러너를 import 하지는 않는다."""
    lines = [line.strip() for line in prompt.splitlines()]
    if not any(_NEW_SESSION.match(line) for line in lines):
        return None
    return _branch_of(lines)


def _branch_of(lines: list[str]) -> str | None:
    """`브랜치:` 줄의 값. 감싼 백틱은 벗긴다. 줄이 없거나 값이 비었으면 None."""
    for line in lines:
        if line.startswith(_BRANCH_LINE):
            value = line.removeprefix(_BRANCH_LINE).strip().strip("`").strip()
            return value or None
    return None


def _folder_key(path: str) -> str:
    """폴더 비교 키. 구분자를 `/` 로, 끝의 구분자를 떼고, 대소문자를 접는다.

    윈도 경로라 대소문자를 가리지 않는다. `os.path` 에 맡기지 않는 이유는 그 정규화가 운영체제마다
    달라 CI 와 이 PC 가 다른 답을 내기 때문이다. 정규화하지 않는 표기(`..`, UNC, `/c/`)는 다르다고
    나와 막는 쪽으로 틀린다.
    """
    return path.replace("\\", "/").rstrip("/").casefold()


def _fullwidth_skill(prompt: str) -> str | None:
    """첫 글자가 전각 `／` 이고 바로 뒤가 kebab 이름 하나면 그 이름.

    이름이 곧 경로라 좁게 받는다.
    """
    head = prompt.lstrip()
    if not head.startswith(FULLWIDTH_SLASH):
        return None
    match = _SKILL_NAME.match(head, len(FULLWIDTH_SLASH))
    return match.group(1) if match is not None else None


def is_first_turn(transcript_path: str | None) -> bool:
    """이 세션에서 모델이 아직 한 번도 답하지 않았는가.

    두 부재를 반대로 판정한다. 파일이 아직 없으면 첫 턴이다 — 새 세션의 첫 프롬프트에서는
    트랜스크립트가 만들어지기 전일 수 있다. 경로 키가 없으면 첫 턴을 증명할 수 없으니 아니라고
    본다. 잘못 발동하면 엉뚱한 세션의 이름이 조용히 바뀌고, 발동하지 않으면 앱이 지은 제목이 남아
    open-session 4단계의 확인이 알린다. 빈 경로도 모르는 것이다(`Path("")` 는 작업 디렉터리다).
    """
    if not transcript_path:
        return False
    path = Path(transcript_path)
    if not path.exists():
        return True
    with path.open(encoding="utf-8", errors="replace") as transcript:
        return not has_assistant_turn(transcript)


def has_assistant_turn(lines: Iterable[str]) -> bool:
    """트랜스크립트 JSONL 에 assistant 기록이 하나라도 있으면 True. 첫 것에서 멈춘다."""
    return any(_record_type(line) == "assistant" for line in lines)


def _record_type(line: str) -> str | None:
    """JSONL 한 줄의 최상위 `type`. JSON 객체가 아니면 None.

    `{` 로 시작하는 올바른 JSON 은 객체뿐이라 주해가 참이다. 본문 문자열 속의 같은 글자는
    세지 않는다.
    """
    if not line.lstrip().startswith("{"):
        return None
    try:
        record: TranscriptRecord = json.loads(line)
    except ValueError:
        return None
    return record.get("type")


def main() -> int:
    # 훅 환경에 PYTHONUTF8 이 없으면 텍스트 stdin 이 cp949 로 읽힌다. 그러면 한글이 깨져
    # `브랜치:` 가 매치되지 않고, 예외 없이 exit 0 에 출력 0바이트로 계기가 사라진다(실측).
    # 바이트로 받아 JSON 이 UTF-8 로 풀게 한다.
    payload: HookPayload = json.load(sys.stdin.buffer)
    prompt = payload.get("prompt", "")
    # 막기는 첫 턴을 보지 않는다. 옮긴 첫 줄은 open-session 만 만들고, 폴더가 다르면 몇 번째 턴이든
    # 엉뚱한 저장소에서 스킬을 따르게 된다. 막으면 프롬프트가 지워지고 이유는 사람에게만 보인다.
    reason = block_reason_for(prompt, payload.get("cwd"))
    if reason is not None:
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0
    context = first_turn_context(
        prompt,
        payload.get("cwd"),
        payload.get("transcript_path"),
        os.environ.get(ATTENDED_VAR),
        os.environ.get(HEADLESS_MARKER),
    )
    if context is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
