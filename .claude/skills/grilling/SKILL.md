---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

<!-- 프로젝트 사본. agent-os가 덧댄 판을 2026-11-09 킥오프에서 옮겼고, 이 주석과 본문의 괄호 속 일지·대기열 번호는 agent-os의 기록이다. agent-os의 `CLAUDE.md` 원칙에 있던 쉬운 말 규칙과 기술 개념 풀이 규칙은 이 저장소의 `CLAUDE.md`에 없어, 라운드 문단에 그 내용을 옮겨 적었다. 원본(mattpocock/skills)의 텍스트 라운드 형식을 `AskUserQuestion` 라운드로 바꿨다. 사용자가 설계 인터뷰에서 UI로 고르는 선택지와 추천을 요청했는데 그 선호가 일지에만 있어서, 이 스킬의 텍스트 형식을 따른 세션이 같은 라운드를 UI로 다시 올렸다(일지 2026-09-22-07, 2026-09-24-03, 2026-09-26-06, 대기열 27). 사실을 찾는 서브에이전트의 보고를 근거의 종류로 가르고 조합은 소비 지점까지 재게 하는 문단을 더했다(대기열 45·61, 웹 요약은 124). 호출 곁 본문에 처음 나오는 기술 개념의 풀이를 두는 자리를 더했다(대기열 114). 선택지 설명의 사실을 올리기 전에 대 보고, 답을 옮길 때 설명까지 옮기는 문단을 더했다(대기열 101·46). 질문과 선택지를 쉬운 말로 쓰는 문장과, 쉬운 말에서도 사실을 빼지 않고 명세·ADR에는 용어집의 말로 옮기는 문장을 더했다. 코드 이름으로 쓴 라운드를 사용자가 고르지 못했다(일지 2026-10-15-17). 결정이 절차를 바꾸면 합의 요약 전에 그 절차의 중간으로 들어오는 갈래를 밟는 문단을 더했다(대기열 396). 이 주석이 `tools/check_instructions.py`의 센티널이라 지우면 검사가 빨강이 된다. -->

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round. Then wait for the user's answers before the next round.

라운드는 `AskUserQuestion` 도구로 올린다. 결정 하나가 질문 하나다. 질문마다 네가 추천할 답을 먼저 고르고, 그 선택지를 첫 자리로 옮겨 라벨 끝에 "(Recommended)"를 붙인다. 선택지마다 설명에 그것을 고르면 무엇이 정해지는지 적는다. 질문, 라벨, 설명은 처음 보는 사람이 읽고 바로 판단할 수 있게 쉬운 말과 구체적인 장면(무엇이 보이는지, 무엇이 바뀌는지)으로 쓴다. 라벨은 내부 이름(코드 이름, 형식 번호)이 아니라 고르면 실제로 바뀌는 것이고, 코드 이름은 꼭 필요할 때 괄호로 덧붙인다(라벨은 "요약 실패만 따로 안내"이지 "형식 3 그대로"가 아니다). 한 호출에 넷까지 들어가므로 frontier가 넷을 넘으면 같은 라운드를 호출 여럿으로 잇달아 올린다. 질문 문장은 호출 안에만 쓴다. 호출 곁의 본문에는 선택지가 담지 못하는 것, 곧 네가 찾은 사실과 추천의 근거, 질문에 처음 나오는 기술 개념의 풀이(무엇인가, 잡아 주는 것, 치르는 값)만 쓴다.

결정의 조건은 라벨이 아니라 선택지의 설명에 있다.

- **올리기 전.** 설명에 넣는 사실(지금 코드가 무엇을 하는지, 도구가 언제 무엇을 읽는지, 판정자가 막는지, 선례)은 지금 코드와 판정자(린터, 타입 검사, 훅)에 대 본다. 선례를 들면 반대 방향의 선례도 찾는다. 쉬운 말로 풀 때도 대 본 사실과 반대 방향의 선례를 빼지 않는다. 확인하지 못한 사실은 설명에 어림이라고 적는다. 설명의 사실을 대 보지 않은 일이 세 세션에서 있었다. 저장소의 주석이 이미 반박한 전제(헤더가 시작 때 읽힌다), 반대 방향의 선례를 빠뜨린 트레이스 형식, 지금 코드에 대 보지 않은 anyio 5의 변경, 지금 화면과 다른 설명(걸린 시간), ESLint가 막는 인라인 스크립트다(대기열 101).
- **옮길 때.** 답을 다른 자리(일지의 `> 사용자:` 인용, 명세, ADR, 리뷰 브리프)로 옮길 때는 라벨과 함께 고른 선택지의 설명을 글자 그대로 옮기고, 요약을 확인받은 질문이면 그 요약도 옮긴다. 설명과 요약은 에이전트가 쓴 글이라, 일지 인용에서는 사용자가 고른 라벨만 따옴표 안에 두고 설명은 그 뒤에 `— 설명:`으로 붙인다. 라벨만 넘긴 명세에서 리뷰가 설명과 요약에 있던 결정을 범위 넘침으로 냈다(대기열 46). 다만 명세와 ADR에는 쉬운 말을 용어집의 말로 옮겨 적을 수 있다. 그때도 설명과 요약의 조건은 하나도 빼지 않고, 원문은 일지의 인용을 가리킨다. 고른 설명이 기술 조건을 틀리게 적었으면 옮기기 전에 그 질문을 다시 묻거나 합의 요약에서 바로잡아 확인받는다.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

사실을 찾는 서브에이전트에게는 보고를 근거의 종류로 갈라 달라고 한다. 스크립트로 쟀다(그 파일), 손으로 봤다(그 명령), 코드를 읽었다(파일과 판), 어림이다, 웹 요약이다(그 주소. WebFetch가 준 수와 인용은 원문을 받아 대 보기 전에는 이것이다). 고르는 사실이 라이브러리나 도구의 조합이면 그것을 쓰는 코드가 타입 검사와 실행을 지나는 데까지, 설치할 판으로 재게 한다. 그 보고가 그대로 ADR의 근거가 된다. 규약은 `docs/agents/issue-tracker.md`의 프로브와 근거 절이다(대기열 45·61).

결정이 에이전트가 단계대로 따르는 절차(스킬, 훅, 브랜치와 병합의 규약)를 바꾸면, 합의 요약을 올리기 전에 그 절차의 중간으로 들어오는 갈래를 하나씩 밟는다. 인계로 넘겨받은 세션, 끊은 뒤 이어 가는 세션, 열린 PR을 반영하는 세션, 규약이 면제하는 단계, 규약이 서기 전에 열린 일이다. 갈래마다 새 절차가 시키는 대로 했을 때 어긋나는 동작(건너뛰는 단계, 막히는 커밋, 엉뚱한 세션에 뜨는 알림)이 나면 그것이 아직 열린 가지이고, 다음 라운드의 질문이 된다. 밟는 법은 `code-review` 4단계의 **갈래 밟기** 문단과 같다. 이 갈래를 밟지 않은 설계 인터뷰 뒤에 셀프 리뷰 두 축의 Major 아홉 가운데 여섯이 그 갈래에서 나와, 승인 화면에서 따로 확인받았다(대기열 396).

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
