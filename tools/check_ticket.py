"""커밋 검사: 이 브랜치의 변경이 티켓 하나를 가리키는지 본다(ADR 0037). CI 는 PR 마다 같은 판정을
하고, 가리키는 티켓의 `Status:` 가 done 인지도 본다.

pre-commit 에 항목을 따로 두지 않고 `tools/run_checks.py` 의 `CHECKS` 에 든다(id `check-ticket`).
건너뛰기는 그 id 의 `SKIP` 이다. 작업 폴더의 저장소를 보고, git 을 부를 때 저장소를 가리키는 환경
변수를 벗기지 않는다. git 이 훅에 임시 색인(`GIT_INDEX_FILE`)을 주는 커밋(일부 파일만 커밋하는
`git commit <경로>`, 고친 추적 파일을 모두 싣는 `-a`)에서는 그 색인이 pre-commit 과 러너를 거쳐
여기까지 닿아야 그 커밋에 들 것을 보기 때문이다. CI 는 `.github/workflows/ci.yml` 의 `ticket` 잡이
`--ci` 로 부른다(아래 CI).
명세는 `.scratch/ticket-for-every-pr/spec.md` 의 "면제 모양", "커밋 검사", "전환", "CI" 이고, 판정의
원천은 이 독스트링이다.

바뀐 파일(C). 이 브랜치와 `origin/main` 의 merge-base 에서 지금 색인까지의 차이다. 이름 바꾸기는
지운 것과 더한 것 둘로 센다(rename 감지를 끈다). 켜면 면제 밖의 파일을 면제 모양의 자리로 옮긴
변경이 새 경로 하나로만 보여 지나간다. 병합을 마무리하는 커밋(`MERGE_HEAD` 가 있다)이면
merge-base 를 `git merge-base origin/main HEAD <MERGE_HEAD>` 로 구한다. 충돌을 풀고 친 커밋의
pre-commit 에서 HEAD 는 아직 병합 전이라, HEAD 만으로 구하면 C 에 main 이 들여온 파일이 섞인다.
`MERGE_HEAD` 는 작업 트리 루트의 경로가 아니라 ref 이름으로 찾는다. 링크드 워크트리에서는 그
워크트리의 git 디렉터리에 있어, 루트의 `.git/MERGE_HEAD` 로 찾으면 놓친다
(`.scratch/ticket-for-every-pr/probes/merge_commit/`). 공통 조상이 없으면(고아 브랜치) 빈 트리에서
지금 색인까지다. 그 브랜치의 파일은 모두 그 브랜치가 들인 것이다. 얕은 클론(클라우드 세션의 깊이
50 클론)에서는 딴 자리가 깊이 밖이면 공통 조상이 없어 보여, 빈 트리에서 세면 C 가 저장소 전체가
된다. 그래서 얕은 클론에서 공통 조상을 찾지 못하면 한 줄을 알리고 판정하지 않고 지난다.

판정. 아래 차례로 처음 맞는 것이다.

1. 분리 HEAD 이거나 브랜치가 main 이나 dev 이면 지난다. 그 위의 커밋은
   `tools/hook_git_main_commit.py` 가 막는다.
2. 기준 ref 를 찾지 못하면 한 줄을 알리고 지난다. 로컬 판정의 기준 ref 는 agent-os ADR 0043 의
   규칙이다. `hotfix/*` 는 `origin/main`, 그 밖은 `origin/dev` 가 있으면 그것, 없으면 `origin/main`
   이다(dev 가 서기 전이나 이 클론이 받은 적이 없는 때도 main 으로 돈다). 아래 설명의 `origin/main`
   은 이 기준 ref 로 읽는다. CI 의 판정은 받은 base 커밋이 기준이라 이 규칙을 쓰지 않는다. 원격 없이
   연습하는 클론이다. 그 클론이 연 PR 은 CI 가 같은 판정을 한다. HEAD 가 아직 커밋을 가리키지
   않아도(고아 브랜치의 첫 커밋) 한 줄을 알리고 지난다. 딴 자리가 없어 전환을 가르지 못한다.
3. 규약 전에 연 브랜치면 한 줄을 알리고 지난다(아래 전환).
4. C 가 비었거나 모두 면제 모양이면 지난다.
5. 티켓 모양 브랜치는 그 티켓이 C 에 있고 색인에 남아 있어야 지난다. `feature/NN-<slug>` 는
   `.scratch/<어느 slug>/issues/NN-<slug>.md` 다. `chore/` 뒤의 글자는 그대로 stem 이고 티켓은
   `.scratch/harness/issues/<stem>.md` 다. 새 꼴 `chore/<slug>` 와 옛 꼴
   `chore/045-ci-python-runner-pin` 이 같은 규칙 하나로 맞는다. 핫픽스 브랜치 `hotfix/<slug>` 도
   `chore/` 와 같은 자리의 티켓 `.scratch/harness/issues/<slug>.md` 를 가리킨다(agent-os ADR 0043).
   핫픽스는 기준 브랜치가 main 이라(`base_ref`) 접두를 `chore/` 로 바꾸지 못해 접두가 따로 선다.
   핫픽스가 고치는 것이 기능의 동작이어도 티켓은 harness 폴더에 둔다(ADR 0016 이 agent-os 와 같이
   정했다. `docs/agents/issue-tracker.md` 의 "기능 밖에서 제품 코드를 고치는 일" 항목은 기능
   디렉터리의 티켓을 말해 핫픽스와 다르다). 지운 티켓은 가리키지 않은 것으로 본다.
6. `docs/<slug>` 브랜치는 C 에 harness 티켓(`.scratch/harness/issues/<slug>.md`, 옛 꼴
   `NNN-<slug>.md`)이 하나라도 있으면 지난다. slug 는 영어 소문자로 시작하는 이름(대기열 항목과
   같은 규칙)이다. 더한 것이든 고친 것이든 세고, 지운 것은 세지 않는다. 회고가 고침을 반영해 같은
   PR 에 쓴 티켓이다. 번호와 브랜치 이름은 맞대지 않는다. 그 폴더의 다른 파일(`README.md`, 하위
   폴더, `.md` 가 아닌 것)은 티켓이 아니다.
7. 그 밖은 막는다. 앱 워크트리 모양(`claude/<이름>`)과 `worktree-<이름>` 도 여기다.

면제 모양. 이 목록이 모양의 원천이다(`docs/agents/issue-tracker.md` 가 여기를 가리킨다). 기능의
설계·명세·티켓을 쓰는 PR 과 기록만 남기는 PR 이 쓰는 파일이다.

- `docs/journal/*.md`, `.scratch/retro-queue/*.md`
- `docs/adr/*.md`(색인 `README.md` 포함), `GLOSSARY.md`, `docs/PRD.md`
- `.scratch/plan.md`(도구가 만든 전체 계획), `.scratch/plan-head.md`(그 손 파일)
- `docs/constitution/tech.md`, `docs/constitution/README.md`, `docs/constitution/history.md`(헌법 판
  이력의 기록. README 에서 옮겨 온 것이라 더하지 않고, 판을 올린 까닭은 ADR 이력이나 일지에 적는다)
- `.scratch/<slug>/spec.md`, `.scratch/<slug>/plan.md`(기능 계획), `.scratch/<slug>/issues/*.md`,
  `.scratch/<slug>/probes/**`, `.scratch/<slug>/design/**`. 이 다섯은 `<slug>` 가 `harness` 이면
  면제가 아니다.
  `.scratch/harness/issues/` 는 하는 일의 티켓이 사는 자리이고 `.scratch/harness/probes/` 는 하네스
  도구를 받치는 측정이라 그 도구를 고치는 티켓에 든다. `<slug>` 가 `retro-queue` 여도 면제가
  아니다. 그 폴더는 기능이 아니라 회고 반영 대기열(항목마다 파일 하나)이라, 바로 아래의 `.md` 만
  면제이고 `.scratch/retro-queue/issues/x.md` 같은 꼴은 면제가 아니다.

`*` 는 경로 조각 하나이고 `**` 는 그 아래 전부다. 표에 없는 기능 폴더의 파일(`design.md`, `mock/`)은
면제가 아니다. 대기열 폴더의 하위 폴더(`.scratch/retro-queue/sub/x.md`), `.md` 가 아닌 파일, 비슷한
이름의 폴더(`.scratch/retro-queue-x/x.md`), 이행 전의 표 파일 `.scratch/retro-queue.md` 도 면제가
아니다.

전환. 규약 전에 연 브랜치는 그 브랜치의 첫 자기 커밋의 부모 트리에 이 파일
(`tools/check_ticket.py`)이 없는 것으로 가른다. 첫 자기 커밋은 `origin/main` 에 없는 이 브랜치의
커밋 가운데 부모가 모두 `origin/main` 쪽에 있는 것이다. 커밋 날짜가 아니라 위상 순서로 가르는 것은
날짜가 rebase 와 시계에 따라 움직여서다. 그런 커밋이 여럿이면(다른 브랜치를 합친 브랜치) 모두의
부모 트리에 이 파일이 없을 때만 규약 전이다. 부모가 없는 첫 자기 커밋(고아 브랜치의 뿌리)은 딴
자리가 없어 그 커밋 자신의 트리로 가른다. `git checkout --orphan` 은 색인을 그대로 두어 뿌리 커밋이
이 파일을 든 채로 시작하고, 빈 트리로 보면 그 브랜치와 그 역사를 합친 브랜치가 끝까지 지난다. 자기
커밋이 아직 없으면 HEAD 를 그 자리로 본다.
merge-base 의 트리로 가르지 않는다. main 을 합치면 merge-base 가 앞으로 와서 그 순간 막힌다. 규약 전
브랜치를 검사가 든 main 으로 rebase 하면 첫 자기 커밋의 부모가 새 main 이 되어 판정을 받는다. 딴
자리가 옮겨진 것이라 그대로 두고, 막히면 막는 글의 길을 따른다.

CI. `--ci` 로 부르면 PR 의 값을 환경 변수로 받아 PR 단위로 같은 판정을 한다. `PR_HEAD_REF` 는 머리
브랜치 이름, `PR_HEAD_SHA` 는 머리 커밋, `PR_BASE_SHA` 는 base 커밋이다. 판정 전체의 기준은
`origin/main` 대신 base 커밋이고, 브랜치 이름과 HEAD 는 머리 브랜치와 머리 커밋이 대신한다.
체크아웃한 PR 의 병합 커밋은 분리 HEAD 라 판정 1 을 체크아웃으로 보지 않는다. 보면 모든 PR 이
지난다. 머리 커밋을 체크아웃하지 않는 것은 규약 전에 딴 PR 의 머리에는 이 파일이 없어서다. 병합
커밋에는 base 쪽의 이 파일이 있다.
- C 는 base 와 머리의 merge-base 에서 머리 커밋까지의 차이다(색인이 아니라 머리 커밋의 트리).
  전환의 자기 커밋은 base 에 없는 머리의 커밋이고, 첫 자기 커밋은 그 가운데 부모가 모두 base 쪽에
  있는 것이다(위 전환과 같다). 그래서 다른 브랜치를 base 로 둔 PR 은 그 base 브랜치의 커밋을 제
  것으로 세지 않는다.
- 판정 2 의 자리에서 받은 커밋 값이 비었거나 이 저장소에 없으면 git 실패(종료 2)다. CI 의 체크아웃이
  이력을 덜 받은 것이라 지나지 않는다. 체크아웃이 얕아 base 와 머리의 merge-base 를 찾지 못해도
  같다. 커밋 검사의 얕은 클론처럼 알리고 지나면 모든 PR 이 판정 없이 초록이 되기 때문이다. 그래서
  CI 는 전환을 가르기 전에 merge-base 를 구한다. MERGE_HEAD 와 HEAD 가 없는 첫 커밋은 CI 에 없다.
- 판정 5·6 으로 지나면 가리키는 티켓(판정 5 의 그 파일, `docs/` 브랜치면 판정 6 의 harness 티켓
  전부)의 `Status:` 를 머리 커밋의 그 파일에서 읽고, 하나라도 done 이 아니면 막는다. 티켓은 PR 을
  열기 전에 done 이다(명세 "쓰는 때와 상태").
- 판정 전에 받은 세 값과 체크아웃한 병합 커밋의 첫 부모를 stdout 에 한 줄 찍는다. base 값이 그 첫
  부모와 같은지 실제 실행에서 견주기 위해서다.
- 머리 브랜치가 main 이나 dev 인 PR 은 판정 1 로 지난다. dev→main 출시 PR 과 main→dev 되돌려
  합치기는 티켓 하나를 가리키지 않는다(agent-os ADR 0043 Consequences "티켓 검사와 봇"). 그 안의
  티켓 PR 은 dev 로 들어갈 때 이미 판정을 받았다.
- `PR_HEAD_REF` 가 비면(PR 이 아닌 실행, main·dev 의 push) 한 줄을 찍고 지난다. 필수 검사 `verify`
  가 건너뛴 잡을 빨강으로 보므로 이 잡은 push 에서도 돌고 곧바로 끝난다. 다만 러너가 주는 이벤트
  이름(`GITHUB_EVENT_NAME`, GitHub 문서 Variables reference 의 기본 환경 변수 표. 2026-10-22 에
  본문을 내려받아 대 봤다)이 `pull_request` 인데 비면 git 실패(종료 2)다. 워크플로의 env 이름이
  어긋나거나 식이 빈 것이고, 지나면 모든 PR 이 판정 없이 초록이다.

`Status:` 를 읽는 규칙. 값은 줄 머리가 `Status:` 나 `**Status:**` 인 첫 줄의 첫 낱말이다. 줄
어디서든 첫 출현을 읽지 않는다. 티켓이 수용 기준 본문(기능을 닫는 판정의 문장)이나 설명에 `Status:`
를 한 번 더 들고, 그 자리가 상태 줄보다 앞인 티켓도 있다(`.scratch/ticket-for-every-pr/issues/` 의
04). 그런 줄이 없거나 값이 비었거나 첫 낱말이 글자 그대로 `done` 이 아니면 done 이 아니다.

막는 글(stderr). 판정 7 은 면제 모양 밖의 바뀐 파일(앞의 열 개와 나머지 수), 브랜치가 티켓 모양이면
찾은 티켓 경로, 티켓을 쓸 자리와 하네스 티켓의 slug 를 번호 없이 짓는 규칙, 브랜치 이름을 바꾸는
명령, 규약 원천을 싣는다.
가리키는 티켓 파일이 디스크에는 있는데 C 에 없으면 그 티켓의 `Status:` 를 in-progress 로 고치고
스테이지하라는 알림을 더한다. 고치지 않은 것과 고치고 스테이지하지 않은 것을 가르지 않는다.
pre-commit 은 훅이 도는 동안 스테이지하지 않은 고침을 치워 둘이 커밋에서 갈리지 않는다. CI 에서는
머리 줄이 "PR 을 막았다" 이고, 알림은 머리 커밋의 트리에 있는데 C 에 없는 티켓에 대해 `Status:` 를
done 으로 고쳐 커밋하고 다시 푸시하라는 것이다(이미 done 이면 앞서 닫힌 티켓이라 이 PR 의 티켓을
새로 쓰라고 한다). CI 가 done 이 아닌 티켓으로 막으면 그 티켓 경로와
지금 값, done 으로 고쳐 다시 푸시하라는 할 일, 규약 원천을 싣는다. 판정과 git 실패의 출력은 첫 줄이
`check-ticket: ` 으로 시작한다. 인자를 잘못 주면 argparse 가 사용법을 그 접두 없이 찍는다.

러너에 둔 값. 러너는 한 검사가 실패해도 나머지를 끝까지 기다리므로, 막히는 커밋은 러너 한 바퀴 뒤에
글이 보이고 고친 뒤 한 바퀴를 더 돈다. 러너가 곧바로 멈추기를 들이면(대기열 192) 이 값은 사라진다.
변경을 마치고 손으로 친 러너에서도 이 검사가 지금 색인으로 돌아, 티켓을 스테이지하기 전이면 빨갛다.

종료 코드. 0 지남, 1 막음, 2 git 이 실패했다(띄우지 못함, 시간 초과, 판정에 쓰는 git 의 0 아닌
종료. 저장소가 아닌 폴더, CI 가 받은 커밋 값을 찾지 못한 것, CI 의 얕은 체크아웃, PR 실행의 빈
`PR_HEAD_REF` 도 여기다). 인자를 잘못 준 것도 argparse 가 2 로 끝낸다.

못 보는 것.
- pre-commit 을 거치지 않은 커밋은 커밋 때 지난다. 훅을 깔지 않은 클론, `--no-verify`, 이 id 의
  `SKIP`, 충돌 없는 `git merge` 의 병합 커밋(이 저장소는 pre-merge-commit 훅을 깔지 않는다)이다.
  그 커밋이 든 PR 은 CI 가 같은 판정으로 잡는다.
- 티켓의 내용(수용 기준이 맞는지)은 보지 않는다. `Status:` 는 CI 만 보고, 커밋 검사는 보지 않는다.
- `docs/` 브랜치에 harness 티켓을 하나 쓰거나 이미 있는 harness 티켓을 고치기만 하고 회고 반영이
  아닌 일을 실어도 지난다.
- 고아 브랜치(`git checkout --orphan`)의 첫 커밋은 HEAD 가 없어 지난다(판정 2). 그 뒤의 커밋은
  뿌리 커밋의 트리로 전환을 가른다. 색인을 비우고(`git rm -r --cached .`) 만든 뿌리는 이 파일이 없어
  규약 전으로 지난다.
- 면제 모양만 고치는 PR 은 고침이 무엇이든 지난다(ADR 의 오타 고침, `GLOSSARY.md` 의 말 고침). CI 도
  그 PR 의 티켓 `Status:` 를 보지 않는다.
- 커밋 검사는 얕은 클론에서 딴 자리가 깊이 밖이면 판정하지 않고 지난다(위 C). 그 클론의 고아
  브랜치도 같다. `git fetch --deepen` 이나 `--unshallow` 로 딴 자리를 가져오면 판정을 받는다. CI 는
  지나지 않는다(위 CI).
- 지나는 갈래가 내는 한 줄(전환, `origin/main` 없음, 얕은 클론)은 러너가 통과한 검사의 출력을 찍지
  않아 커밋과 손으로 친 러너에서 보이지 않고, 이 검사를 바로 칠 때와 CI 잡의 로그에서 보인다.
- 검사가 main 에 들어온 뒤에도 그 전의 main 에서 딴 브랜치(가져오지 않은 `origin/main` 에서 딴 것)는
  딴 자리의 트리에 이 파일이 없어, 커밋 검사와 CI 모두에서 끝까지 지난다.
- CI 에서 머리 브랜치가 main 이나 dev 인 PR(포크의 main·dev 에서 연 것)은 판정 1 로 지난다. main·dev
  위 커밋을 막는 훅(`tools/hook_git_main_commit.py`)은 이 저장소의 Claude 세션 훅이라, 포크의
  main·dev 에서 친 커밋이 그 훅을 거쳤다고 볼 수 없다.
- 다른 브랜치 위에 쌓은 브랜치의 커밋은 커밋 검사가 `origin/main` 에 견줘 base 브랜치의 변경까지
  센다. 그래서 면제 모양만 고친 커밋도 base 브랜치가 든 면제 밖 파일 때문에 막힌다(거짓 양성).
  커밋 검사는 그 브랜치가 PR 에서 무엇을 base 로 둘지 모른다. 그 PR 은 CI 가 base 커밋에 견줘
  지난다. 다만 base 브랜치가 squash 로 병합되어 PR 의 base 가 main 으로 바뀐 뒤에는, base 브랜치의
  커밋이 main 에 없어 CI 도 그 변경을 이 PR 의 것으로 세어 막는다(거짓 양성). 막는 글의 할 일(티켓
  쓰기, 브랜치 이름 바꾸기)은 이 경우의 길이 아니다.
  `git rebase --onto origin/main <옛 base 브랜치>`(PR 의 새 base 가 dev 이면 `origin/dev`)로 이
  브랜치의 커밋만 옮겨 강제 푸시
  (`git push --force-with-lease`)하면 지난다. 이미 푸시한 커밋을 고쳐 쓴 것이라 빨리 감기가 아니다.
  옛 base 브랜치를 이미 지웠으면 그 이름 대신 옛 base 의 끝 커밋을 준다. base 만 바꾸는 것은
  워크플로의 `pull_request` 기본 계기(opened, synchronize, reopened)가 아니라서 CI 가 다시 돌지
  않고, 다음 푸시에서 돈다.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TextIO

CHECK_PATH = "tools/check_ticket.py"
BASE = "refs/remotes/origin/main"
DEV_BASE = "refs/remotes/origin/dev"
# 보호 브랜치. 이 브랜치 위의 커밋은 `tools/hook_git_main_commit.py` 가 막고, CI 의 머리 브랜치가
# 이것이면 티켓 하나를 가리키지 않는 PR(dev→main 출시 PR, main→dev 되돌려 합치기)이라 지난다.
PROTECTED_BRANCHES = frozenset({"main", "dev"})
HOTFIX_PREFIX = "hotfix/"
GIT_TIMEOUT = 60.0
SHOWN = 10
PREFIX = "check-ticket: "
PR_HEAD_REF = "PR_HEAD_REF"
PR_HEAD_SHA = "PR_HEAD_SHA"
PR_BASE_SHA = "PR_BASE_SHA"
EVENT_NAME = "GITHUB_EVENT_NAME"
PR_EVENT = "pull_request"
DONE = "done"
CONVENTION = "규약 원천: docs/agents/issue-tracker.md"

_EXEMPT_FILES = frozenset(
    {
        "GLOSSARY.md",
        ".scratch/plan.md",
        ".scratch/plan-head.md",
        "docs/PRD.md",
        "docs/constitution/tech.md",
        "docs/constitution/README.md",
        "docs/constitution/history.md",
    }
)
_HARNESS_ISSUES = ".scratch/harness/issues/"
_QUEUE_FOLDER = "retro-queue"
# 기능 폴더의 갈래(명세·티켓·프로브·디자인)가 기능 slug 로 읽지 않는 `.scratch/` 아래 폴더
_NOT_FEATURES = frozenset({"harness", _QUEUE_FOLDER})
_STATUS_HEADS = ("Status:", "**Status:**")
# 새 꼴은 대기열 항목의 slug 규칙(영어 소문자로 시작)이고, 옛 꼴은 세 자리 번호와 하이픈이다
_HARNESS_STEM = re.compile(r"[a-z][a-z0-9-]*|\d{3}-.+")
# 티켓이 `.scratch/harness/issues/<stem>.md` 인 브랜치 접두. `hotfix/<slug>` 는 기준 브랜치가 main
# 이라 (`base_ref`) 접두를 `chore` 로 바꾸면 기준이 dev 로 바뀐다. 그래서 같은 티켓 자리를 쓰는
# 별개의 갈래다
_HARNESS_KINDS = ("chore", "hotfix")


class GitError(Exception):
    pass


@dataclass(frozen=True)
class Change:
    path: str
    deleted: bool


@dataclass(frozen=True)
class PullRequest:
    """CI 가 환경 변수로 받는 PR 의 값."""

    branch: str
    head: str
    base: str


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"git {args[0]} 을 띄우지 못했거나 {GIT_TIMEOUT:.0f}초를 넘겼다: {error}"
        raise GitError(message) from error


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").strip()


def _out(cwd: Path, *args: str) -> str:
    result = _git(cwd, *args)
    if result.returncode != 0:
        message = _text(result.stderr)
        raise GitError(f"git {' '.join(args)} 가 {result.returncode} 로 끝났다: {message}")
    return _text(result.stdout)


def _fields(cwd: Path, *args: str) -> list[str]:
    """`-z` 로 친 git 의 출력을 NUL 로 가른 조각. 경로의 앞뒤 공백을 지우지 않는다."""
    result = _git(cwd, *args)
    if result.returncode != 0:
        message = _text(result.stderr)
        raise GitError(f"git {args[0]} 가 {result.returncode} 로 끝났다: {message}")
    return result.stdout.decode("utf-8", "replace").split("\0")


def _maybe(cwd: Path, *args: str) -> str | None:
    """성공하면 출력, 아니면 None. 있는지 묻는 git 에 쓴다."""
    result = _git(cwd, *args)
    if result.returncode != 0:
        return None
    return _text(result.stdout)


def _commit(cwd: Path, rev: str) -> str | None:
    """그 이름이 가리키는 커밋, 없으면 None."""
    return _maybe(cwd, "rev-parse", "-q", "--verify", f"{rev}^{{commit}}")


def exempt(path: str) -> bool:
    """면제 모양인가. 모양은 모듈 독스트링이 원천이다."""
    if path in _EXEMPT_FILES:
        return True
    parts = path.split("/")
    if len(parts) == 3 and parts[0] == "docs" and parts[1] in ("journal", "adr"):
        return parts[2].endswith(".md")
    if len(parts) == 3 and parts[:2] == [".scratch", _QUEUE_FOLDER]:
        return parts[2].endswith(".md")
    if len(parts) >= 3 and parts[0] == ".scratch" and parts[1] not in _NOT_FEATURES:
        rest = parts[2:]
        if rest in (["spec.md"], ["plan.md"]):
            return True
        if len(rest) == 2 and rest[0] == "issues":
            return rest[1].endswith(".md")
        return len(rest) >= 2 and rest[0] in ("probes", "design")
    return False


def ticket_stem(branch: str) -> tuple[str, str] | None:
    """티켓 모양 브랜치면 (갈래, stem). 갈래는 `feature`, `chore`, `hotfix` 다. `chore/` 와
    `hotfix/` 뒤의 글자는 그대로 harness 티켓의 stem 이라 옛 꼴(`chore/045-ci-python-runner-pin`)과
    새 꼴 (`chore/<slug>`, `hotfix/<slug>`)이 같은 규칙이다. 그 규칙(`_HARNESS_STEM`)에 맞지 않는
    이름(`chore/Foo`, `chore/09-x`, `hotfix/Foo`)은 티켓 모양이 아니다."""
    kind, _, stem = branch.partition("/")
    if kind not in ("feature", *_HARNESS_KINDS) or not stem or "/" in stem:
        return None
    if kind in _HARNESS_KINDS:
        return (kind, stem) if _HARNESS_STEM.fullmatch(stem) else None
    number, dash, slug = stem.partition("-")
    if len(number) != 2 or not (number.isascii() and number.isdigit()) or not dash or not slug:
        return None
    return kind, stem


def is_harness_ticket(path: str) -> bool:
    """`.scratch/harness/issues/` 바로 아래의 티켓 파일인가. 새 꼴 `<slug>.md` 나 옛 꼴
    `NNN-<slug>.md` 다. `README.md` 와 하위 폴더, `.md` 가 아닌 파일은 티켓이 아니다."""
    folder, _, name = path.rpartition("/")
    stem, dot, extension = name.rpartition(".")
    return (
        f"{folder}/" == _HARNESS_ISSUES
        and dot == "."
        and extension == "md"
        and _HARNESS_STEM.fullmatch(stem) is not None
    )


def points_at(kind: str, stem: str, path: str) -> bool:
    """이 경로가 그 브랜치가 가리키는 티켓인가."""
    if kind in _HARNESS_KINDS:
        return path == f"{_HARNESS_ISSUES}{stem}.md"
    parts = path.split("/")
    return (
        len(parts) == 4
        and parts[0] == ".scratch"
        and parts[2] == "issues"
        and parts[3] == f"{stem}.md"
    )


def pointed(branch: str, present: list[str]) -> list[str]:
    """판정 5·6 이 찾은 티켓. 티켓 모양 브랜치는 그 티켓이고, `docs/` 브랜치는 harness 티켓
    전부다."""
    stem = ticket_stem(branch)
    if stem is not None:
        return [path for path in present if points_at(*stem, path)]
    if branch.startswith("docs/"):
        return [path for path in present if is_harness_ticket(path)]
    return []


def tickets_on_disk(root: Path, branch: str) -> list[str]:
    """작업 트리에 있는, 그 브랜치가 가리키는 티켓 파일."""
    stem = ticket_stem(branch)
    if stem is None:
        return []
    kind, name = stem
    pattern = f"harness/issues/{name}.md" if kind in _HARNESS_KINDS else f"*/issues/{name}.md"
    found = sorted((root / ".scratch").glob(pattern))
    return [p.relative_to(root).as_posix() for p in found if p.is_file()]


def tickets_in_tree(cwd: Path, head: str, branch: str) -> list[str]:
    """머리 커밋의 트리에 있는, 그 브랜치가 가리키는 티켓 파일."""
    stem = ticket_stem(branch)
    if stem is None:
        return []
    listing = _fields(
        cwd, "ls-tree", "--full-tree", "-r", "--name-only", "-z", head, "--", ".scratch"
    )
    return [path for path in listing if path and points_at(*stem, path)]


def merge_head(cwd: Path) -> str | None:
    """병합을 마무리하는 중이면 MERGE_HEAD 의 커밋. 링크드 워크트리에서도 ref 이름으로 찾는다."""
    return _commit(cwd, "MERGE_HEAD")


def _changes(cwd: Path, *diff: str) -> list[Change]:
    fields = _fields(cwd, "diff", "--name-status", "--no-renames", "-z", *diff, "--")
    return [
        Change(path, status == "D")
        for status, path in zip(fields[0::2], fields[1::2], strict=False)
        if path
    ]


def staged_changes(cwd: Path, base: str) -> list[Change]:
    """merge-base 에서 지금 색인까지(커밋 검사). 이름 바꾸기는 지운 것과 더한 것 둘이다."""
    return _changes(cwd, "--cached", base)


def tree_changes(cwd: Path, base: str, head: str) -> list[Change]:
    """merge-base 에서 머리 커밋까지(CI). 이름 바꾸기는 지운 것과 더한 것 둘이다."""
    return _changes(cwd, base, head)


def merge_base(cwd: Path, base: str, heads: list[str]) -> str | None:
    """C 를 셀 자리. 공통 조상이 없으면(`merge-base` 가 1 로 끝난다) 빈 트리다. 얕은 클론이면
    조상이 깊이 밖에 있을 수 있어 자리를 모른다(None)."""
    result = _git(cwd, "merge-base", base, *heads)
    if result.returncode == 0:
        return _text(result.stdout)
    if result.returncode == 1:
        if _out(cwd, "rev-parse", "--is-shallow-repository") == "true":
            return None
        return _out(cwd, "hash-object", "-t", "tree", "--stdin")
    message = _text(result.stderr)
    raise GitError(f"git merge-base 가 {result.returncode} 로 끝났다: {message}")


def _has_check(cwd: Path, commit: str) -> bool:
    return _git(cwd, "cat-file", "-e", f"{commit}:{CHECK_PATH}").returncode == 0


def before_convention(cwd: Path, head: str, base: str) -> bool:
    """브랜치를 딴 자리(첫 자기 커밋의 부모, 자기 커밋이 없으면 머리)의 트리에 이 검사가 없는가.
    자기 커밋은 `base` 에 없는 `head` 의 커밋이다."""
    listing = _out(cwd, "rev-list", "--parents", head, "--not", base)
    own: dict[str, list[str]] = {}
    for line in listing.splitlines():
        commit, *parents = line.split()
        own[commit] = parents
    if not own:
        return not _has_check(cwd, head)
    firsts = [commit for commit, parents in own.items() if not any(p in own for p in parents)]
    # 부모 없는 자기 커밋(고아 브랜치의 뿌리)은 딴 자리가 없어 그 커밋 자신의 트리로 가른다
    return all(not _has_check(cwd, own[commit][0] if own[commit] else commit) for commit in firsts)


def status_of(text: str) -> str | None:
    """줄 머리가 `Status:` 나 `**Status:**` 인 첫 줄의 첫 낱말. 그런 줄이 없으면 None, 값이 비면
    빈 문자열이다."""
    for line in text.splitlines():
        for head in _STATUS_HEADS:
            if line.startswith(head):
                words = line.removeprefix(head).split()
                return words[0] if words else ""
    return None


class Outcome(Enum):
    PASS = "지남"
    NOTE = "알리고 지남"
    BLOCK = "막음"


@dataclass(frozen=True)
class Verdict:
    outcome: Outcome
    message: str = ""


_PASS = Verdict(Outcome.PASS)
_SHALLOW = Verdict(Outcome.NOTE, "얕은 클론이라 merge-base 를 찾지 못해 판정하지 않고 지난다.")


def _note(message: str) -> Verdict:
    return Verdict(Outcome.NOTE, message)


def _transition(branch: str) -> Verdict:
    return _note(f"규약 전에 연 브랜치({branch})라 판정하지 않고 지난다.")


@dataclass(frozen=True)
class Wording:
    """막는 글에서 커밋 검사와 CI 가 달리 쓰는 말."""

    blocked: str
    unstaged: str


COMMIT_WORDING = Wording(
    "커밋을 막았다",
    "알림: {path} 가 디스크에는 있지만 이 커밋에 들지 않는다. 그 파일의 `Status:` 를 in-progress 로"
    " 고치고(이미 고쳤으면 그대로) `git add {path}` 로 스테이지한다.",
)
PR_WORDING = Wording(
    "PR 을 막았다",
    "알림: {path} 가 머리 커밋에는 있지만 이 PR 의 변경에 들지 않는다. 그 파일의 `Status:` 를 done"
    " 으로 고쳐 커밋하고 다시 푸시한다. 이미 done 이면 앞서 닫힌 티켓이니 아래 할 일대로 이 PR 의"
    " 티켓을 새로 쓴다.",
)


def _rename_choices(branch: str) -> str:
    """판정 7 의 막는 글이 권하는 새 브랜치 이름의 꼴. `hotfix/*` 는 기준 브랜치가 main
    이라(`base_ref`) 접두를 `feature/` 나 `chore/` 로 바꾸면 PR 의 base 가 dev 로 바뀐다. hotfix 는
    접두를 지킨다."""
    if branch.startswith(HOTFIX_PREFIX):
        return (
            "hotfix/<slug>. 접두를 바꾸면 origin/dev 가 있을 때"
            " 기준 브랜치가 main 에서 dev 로 바뀐다"
        )
    return "feature/NN-<slug> 나 chore/<slug>"


def _blocked(branch: str, outside: list[str], found: list[str], wording: Wording) -> str:
    """판정 7 의 막는 글. `found` 는 그 브랜치가 가리키는데 C 에 들지 않은 티켓이다."""
    lines = [f"브랜치 {branch} 의 변경이 티켓을 가리키지 않아 {wording.blocked}."]
    lines.append(f"면제 모양 밖의 바뀐 파일 {len(outside)}개:")
    lines += [f"  {path}" for path in outside[:SHOWN]]
    if len(outside) > SHOWN:
        lines.append(f"  … 그 밖에 {len(outside) - SHOWN}개")
    stem = ticket_stem(branch)
    if stem is not None:
        kind, name = stem
        expected = (
            f"{_HARNESS_ISSUES}{name}.md"
            if kind in _HARNESS_KINDS
            else f".scratch/<slug>/issues/{name}.md"
        )
        lines.append(f"이 브랜치가 가리키는 티켓: {', '.join(found) or expected}")
        lines += [wording.unstaged.format(path=path) for path in found]
    if branch.startswith(HOTFIX_PREFIX):
        # hotfix 브랜치는 기능 폴더의 티켓을 가리키지 못한다(`ticket_stem`). 기능 코드를 고치는
        # 핫픽스도 harness 자리를 쓴다
        write_ticket = "티켓을 쓴다. 핫픽스의 티켓은 .scratch/harness/issues/<slug>.md 다."
    else:
        write_ticket = (
            "티켓을 쓴다. 기능의 일이면 그 기능 폴더 .scratch/<slug>/issues/NN-<slug>.md, 그 밖의"
            " 하네스 일과 작은 문서 고침이면 .scratch/harness/issues/<slug>.md 다."
        )
    lines += [
        "할 일:",
        f"  1. {write_ticket} 하네스 티켓의"
        " <slug> 는 번호 없이 영어 소문자로 시작하고 소문자·숫자·하이픈만 쓰는 이름을 직접 짓는다.",
        "  2. 브랜치 이름을 티켓 파일 이름의 stem 에 맞춘다: `git branch -m <새 이름>`"
        f"({_rename_choices(branch)}). 이미 푸시했으면 새 이름으로 푸시하고 옛 원격"
        " 브랜치를 지운다. 열린 PR 이 있으면 사람에게 묻는다.",
        CONVENTION,
    ]
    return "\n".join(lines)


def _not_done(path: str, status: str | None) -> str:
    if status is None:
        return f"  {path}: 상태 줄이 없다"
    return f"  {path}: 지금 값 `{status}`" if status else f"  {path}: 상태 줄의 값이 비었다"


def _statuses(cwd: Path, head: str, branch: str, tickets: list[str]) -> Verdict:
    """CI 가 판정 5·6 으로 지난 뒤, 가리키는 티켓이 머리 커밋에서 모두 done 인지 본다."""
    found = [(path, status_of(_out(cwd, "show", f"{head}:{path}"))) for path in tickets]
    open_ = [_not_done(path, status) for path, status in found if status != DONE]
    if not open_:
        return _PASS
    lines = [f"브랜치 {branch} 가 가리키는 티켓이 done 이 아니라 {PR_WORDING.blocked}.", *open_]
    lines += [
        "할 일: 그 티켓의 `Status:` 를 done 으로 고쳐 커밋하고 다시 푸시한다. 티켓은 PR 을 열기"
        " 전에 done 이다.",
        CONVENTION,
    ]
    return Verdict(Outcome.BLOCK, "\n".join(lines))


def current_branch(cwd: Path) -> str | None:
    """브랜치 이름, 분리 HEAD 면 None. `symbolic-ref -q` 는 분리 HEAD 에서 1, 저장소가 아니거나
    git 이 실패하면 128 로 끝나므로 1 만 분리 HEAD 로 읽는다."""
    result = _git(cwd, "symbolic-ref", "-q", "--short", "HEAD")
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        message = _text(result.stderr)
        raise GitError(f"git symbolic-ref 가 {result.returncode} 로 끝났다: {message}")
    return _text(result.stdout)


def base_ref(cwd: Path, branch: str) -> str:
    """로컬 판정이 견주는 기준 ref. agent-os ADR 0043 의 규칙이다. `hotfix/*` 는 `origin/main`, 그
    밖은 `origin/dev` 가 있으면 그것, 없으면(dev 가 서기 전이나 이 클론이 받은 적이 없다)
    `origin/main`."""
    if branch.startswith(HOTFIX_PREFIX):
        return BASE
    return DEV_BASE if _commit(cwd, DEV_BASE) is not None else BASE


def _short(reference: str) -> str:
    """`refs/remotes/origin/dev` → `origin/dev`."""
    return reference.removeprefix("refs/remotes/")


def _outside(changed: list[Change]) -> list[str]:
    return [c.path for c in changed if not exempt(c.path)]


def _present(changed: list[Change]) -> list[str]:
    return [c.path for c in changed if not c.deleted]


def judge(cwd: Path) -> Verdict:
    """커밋 검사. 지금 브랜치와 색인을 `base_ref` 가 고른 기준 ref 에 견줘 판정 1~7 을 한다."""
    branch = current_branch(cwd)
    if branch is None or branch in PROTECTED_BRANCHES:
        return _PASS
    reference = base_ref(cwd, branch)
    if _commit(cwd, reference) is None:
        return _note(f"{_short(reference)} 을 찾지 못해 판정하지 않고 지난다.")
    if _commit(cwd, "HEAD") is None:
        return _note("HEAD 가 아직 없어(첫 커밋) 판정하지 않고 지난다.")
    if before_convention(cwd, "HEAD", reference):
        return _transition(branch)
    heads = ["HEAD"]
    merging = merge_head(cwd)
    if merging is not None:
        heads.append(merging)
    base = merge_base(cwd, reference, heads)
    if base is None:
        return _SHALLOW
    changed = staged_changes(cwd, base)
    outside = _outside(changed)
    if not outside:
        return _PASS
    if pointed(branch, _present(changed)):
        return _PASS
    root = Path(_out(cwd, "rev-parse", "--show-toplevel"))
    found = tickets_on_disk(root, branch)
    return Verdict(Outcome.BLOCK, _blocked(branch, outside, found, COMMIT_WORDING))


def _received(cwd: Path, name: str, value: str) -> str:
    """CI 가 받은 커밋 값을 커밋으로 푼다. 비었거나 이 저장소에 없으면 git 실패다."""
    commit = _commit(cwd, value) if value else None
    if commit is None:
        raise GitError(f"{name} 의 커밋({value or '빈 값'})을 이 체크아웃에서 찾지 못했다.")
    return commit


def judge_pr(cwd: Path, pr: PullRequest) -> Verdict:
    """CI 의 판정. 머리 브랜치와 머리 커밋을 base 커밋에 견줘 판정 1~7 을 하고, 판정 5·6 으로
    지나면 가리키는 티켓이 done 인지 본다."""
    if pr.branch in PROTECTED_BRANCHES:
        return _PASS
    head = _received(cwd, PR_HEAD_SHA, pr.head)
    base = _received(cwd, PR_BASE_SHA, pr.base)
    start = merge_base(cwd, base, [head])
    if start is None:
        raise GitError(
            "CI 의 체크아웃이 얕아 base 와 머리 커밋의 merge-base 를 찾지 못했다."
            " 체크아웃을 fetch-depth: 0 으로 받는다."
        )
    if before_convention(cwd, head, base):
        return _transition(pr.branch)
    changed = tree_changes(cwd, start, head)
    outside = _outside(changed)
    if not outside:
        return _PASS
    present = _present(changed)
    tickets = pointed(pr.branch, present)
    if tickets:
        return _statuses(cwd, head, pr.branch, tickets)
    found = [path for path in tickets_in_tree(cwd, head, pr.branch) if path not in present]
    return Verdict(Outcome.BLOCK, _blocked(pr.branch, outside, found, PR_WORDING))


def pull_request(environ: Mapping[str, str]) -> PullRequest | None:
    """CI 가 받은 PR 의 값. 머리 브랜치가 비었으면(PR 이 아닌 실행) None 이다. 이벤트가 PR 인데
    비었으면 워크플로가 값을 넘기지 못한 것이라 git 실패다."""
    branch = environ.get(PR_HEAD_REF, "")
    if branch:
        return PullRequest(branch, environ.get(PR_HEAD_SHA, ""), environ.get(PR_BASE_SHA, ""))
    if environ.get(EVENT_NAME, "") == PR_EVENT:
        raise GitError(
            f"{EVENT_NAME} 가 {PR_EVENT} 인데 {PR_HEAD_REF} 가 비었다."
            " 워크플로가 PR 의 값을 env 로 넘기는지 본다."
        )
    return None


def judge_ci(cwd: Path, pr: PullRequest | None) -> Verdict:
    """`--ci` 의 판정. PR 이 아닌 실행은 한 줄을 알리고 지난다."""
    if pr is None:
        return _note("PR 이 아닌 실행(main·dev 의 push)이라 판정하지 않고 지난다.")
    return judge_pr(cwd, pr)


def inputs_line(cwd: Path, pr: PullRequest) -> str:
    """CI 가 판정 전에 받은 값과 체크아웃한 병합 커밋의 첫 부모. 실제 실행이 base 값을 그 첫 부모와
    견준다."""
    try:
        parent = _commit(cwd, "HEAD^1") or "없음"
    except GitError as error:
        parent = f"읽지 못했다({error})"
    return (
        f"CI 입력: 머리 브랜치 {pr.branch}, 머리 커밋 {pr.head or '빈 값'},"
        f" base 커밋 {pr.base or '빈 값'}, 체크아웃한 병합 커밋의 첫 부모 {parent}"
    )


def _write(stream: TextIO, message: str) -> None:
    stream.buffer.write(f"{PREFIX}{message}\n".encode())
    stream.buffer.flush()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="커밋 검사(ADR 0037). 판정은 이 파일의 독스트링이다"
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help=f"CI 의 판정. PR 의 값은 환경 변수 {PR_HEAD_REF}, {PR_HEAD_SHA}, {PR_BASE_SHA}"
        " 로 받는다",
    )
    parser.add_argument("cwd", nargs="?", type=Path, help="판정할 저장소. 없으면 작업 폴더")
    return parser


def _run_ci(cwd: Path) -> Verdict:
    """`--ci` 의 실행. PR 의 값을 받아 판정 전에 입력 줄을 찍고 판정한다."""
    pr = pull_request(os.environ)
    if pr is not None:
        _write(sys.stdout, inputs_line(cwd, pr))
    return judge_ci(cwd, pr)


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv[1:])
    ci: bool = args.ci
    where: Path | None = args.cwd
    cwd = Path.cwd() if where is None else where
    try:
        verdict = _run_ci(cwd) if ci else judge(cwd)
    except GitError as error:
        _write(sys.stderr, str(error))
        return 2
    match verdict.outcome:
        case Outcome.PASS:
            return 0
        case Outcome.NOTE:
            _write(sys.stdout, verdict.message)
            return 0
        case Outcome.BLOCK:
            _write(sys.stderr, verdict.message)
            return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
