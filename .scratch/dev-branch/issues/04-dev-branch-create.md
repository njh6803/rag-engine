# 04: 원격 설정을 바꾸고 dev를 main에서 딴다

**What to build:** 01·02·03이 main에 병합된 뒤 ADR 0016의 원격 설정을 걸고 `origin/dev`를 `origin/main`의 머리에서 딴다. agent-os 티켓 5(`dev-branch-create`, #541)의 순서를 따른다. 따는 순간부터 도구가 `origin/dev`를 기준으로 쓴다(01의 규칙).

1. 이 기능 폴더 `issues/`에서 04·05 밖의 티켓(01·02·03과, 01을 쪼개 더한 티켓)의 `Status:`가 모두 done이고 `git log origin/main`에 병합됐는지 본다.
2. **사람의 몫을 다시 보이고 승인을 받는다.** ADR 0016의 원격 설정은 사용자가 설계 인터뷰에서 골랐지만, GitHub 설정은 바꾸기 직전에 다시 승인을 받는다. 승인은 셋을 함께 받고, 거는 때는 셋이 다르다. (가) main의 선형 이력 강제를 끈다. `tools/protection.json`의 `required_linear_history`를 false로 고쳐 승인 직후에 PUT한다. strict는 그대로 둔다(05). (나) dev 보호는 새 파일 `tools/protection-dev.json`(필수 검사 `verify`, strict 끔, 선형 이력 끔, 강제 푸시·삭제 금지, 관리자 우회 허용)으로 둔다. (다) 기본 브랜치를 dev로 옮긴다. (나)와 (다)는 dev가 있어야 걸리므로 3 뒤에 건다.
3. **dev를 딴다.** 먼저 `git ls-remote origin refs/heads/dev`로 dev가 이미 있는지 본다. 끊긴 뒤 이어 하는 세션이면 앞 세션이 이미 땄을 수 있다. 있으면 다시 따지 않고, 그 커밋이 `origin/main`의 머리와 같은지 보고 다르면 사용자에게 보인다. 없으면 `git fetch origin`으로 `origin/main`을 갱신하고 `git push origin origin/main:refs/heads/dev`로 딴다. 로컬 추적 ref가 낡았으면 낡은 커밋에서 dev가 선다. 딴 뒤 `git ls-remote origin refs/heads/main refs/heads/dev`의 두 커밋이 같은지 본다. 그다음 (나)를 PUT하고 (다)를 PATCH한다. 이 단계부터 4가 끝날 때까지는 다른 PR을 main으로 병합하지 않는다.
4. **열린 PR의 base를 옮긴다.** base가 main인 열린 PR 가운데 `hotfix/*`가 아닌 것의 목록을 사용자에게 보인다. 핫픽스 PR은 main에 남는다. 옮기기 직전에 `git ls-remote`로 dev와 main이 아직 같은 커밋인지 다시 보고, 다르면 옮기지 않고 사용자에게 보인다. 같은 커밋이라는 것이 ADR 0016이 옮기는 근거다. 같으면 `gh pr edit <번호> --base dev`로 옮긴다. 그 PR을 연 세션이 돌고 있으면 무엇이 바뀌었는지 알린다. 옮긴 뒤 CI가 다시 도는지, 머리 커밋의 지난 `verify`가 dev 보호에 쓰이는지를 보고 티켓 끝에 적는다(설계 세션은 다시 돌지 않을 것으로 어림했다).
5. `git remote set-head origin dev`를 친다. 이 저장소의 워크트리는 주 체크아웃의 `.git`을 함께 써서 한 번이면 모든 워크트리에 미친다(`git rev-parse --git-common-dir`로 본다). 딴 직후의 보고와 새 세션 지시문의 "확인할 선행 조건"에 `git fetch origin`과 이 명령을 싣는다. 그 뒤 `EnterWorktree`로 만든 워크트리가 dev에서 서는지 본다(`worktree.baseRef`가 기본값 `fresh`일 때 그렇다는 것이 도구 설명이다. 그때의 설정도 적는다).
6. 새 브랜치에서 `uv run python tools/sibling_overlap.py`와 `uv run python tools/check_ticket.py`가 dev를 기준으로 도는지 본다. 이 티켓의 닫는 PR을 dev로 열어 CI의 `ticket` 잡이 지나는지 본다.

**닫을 때 할 일.** 원격 설정을 바꾼 결과(명령의 출력)를 티켓 끝에 적는다. 이 티켓의 PR은 dev를 딴 뒤에 열므로 dev로 간다. 05의 agent-os 조건이 아직 차지 않았으면, 일지의 "다음"에 05가 그 조건을 기다린다는 것과 조건을 보는 명령(05의 `**Blocked by:**`)을 적는다. 하네스 기능은 전체 계획의 표에 들지 않아, 그 줄과 `.scratch/plan-head.md`의 "하네스 기능" 문단이 05를 다시 집게 하는 자리다.

**Blocked by:** 01, 02, 03 (01을 쪼개 더한 티켓이 있으면 그것도)

**Status:** ready-for-agent

- [ ] 원격 설정 (가)~(다)를 사용자에게 다시 보였고 승인을 받은 뒤에 바꿨으며, (나)와 (다)는 dev를 딴 뒤에 걸었고, 응답 값을 티켓 끝에 적었다
- [ ] `origin/dev`가 `origin/main`의 머리에서 섰고, `git ls-remote`로 읽은 두 브랜치의 커밋이 같다
- [ ] dev를 딴 순간 base가 main이던 열린 PR 가운데 `hotfix/*`가 아닌 것이, 두 브랜치가 아직 같은 커밋임을 다시 본 뒤 dev로 옮겨졌고(없었으면 없었다고), 옮긴 뒤 CI와 필수 검사가 어떻게 보였는지 적었다
- [ ] `git remote set-head origin dev` 뒤 `git symbolic-ref refs/remotes/origin/HEAD`가 `refs/remotes/origin/dev`이고, 다른 체크아웃이 칠 두 줄을 보고와 지시문에 실었다
- [ ] dev를 기준으로 `sibling_overlap`·`check_ticket`이 돌고, dev로 연 이 티켓의 PR이 CI를 지났다
- [ ] 검사 넷이 초록이다
