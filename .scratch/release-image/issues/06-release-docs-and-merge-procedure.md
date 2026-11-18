# 06: 운영 문서와 병합 절차가 릴리스의 규칙과 차례와 다시 돌리는 법을 적는다

**What to build:** 릴리스의 규칙이 하네스의 글에 선다. 운영 문서(`docs/constitution/operations.md`)에 두 절이 생긴다. 하나는 릴리스 노트 원고(원고 셋을 누가 언제 싣는지, 느낌표의 기준, 그 기준을 보는 자리)이고, 다른 하나는 릴리스가 나는 차례와 실패한 릴리스를 다시 돌리는 절차다. `docs/constitution/tech.md`에 레지스트리(Docker Hub)와 점검 도구(Grype, Syft)의 행이 생긴다. 병합 절차(`next-session`의 `merge.md`)는 출시 PR과 핫픽스를 병합한 뒤 릴리스를 기다리는 차례와, 출시 PR 앞에 사람 몫이 끝났는지 보는 줄을 갖는다. 이슈 트래커 문서와 구현 스킬은 기능의 마지막 티켓이 기능 단락을 싣는다는 것과 느낌표를 붙이는 때를 적는다(스토리 31, 33, 41, 51, 55).

agent-os 커밋 `1aac0cf`의 같은 절들을 옮겨 이 저장소의 이름(릴리스한다, 제품 변경, 릴리스 노트 원고, 업그레이드)과 값으로 고친다. 하네스의 말(릴리스한다, 제품 변경, 릴리스 노트 원고)의 정의는 운영 문서가 적는다(ADR 0020 "용어"). 이 티켓이 release-image의 첫 티켓이다. 헌법을 바꾸는 티켓은 그 기능의 첫 티켓이며 다른 티켓을 막으므로(`docs/agents/issue-tracker.md`), 이 티켓이 병합되기 전에는 다른 티켓이 시작하지 않는다.

근거는 명세 "규약 문서와 낡은 문장"의 첫 셋과 넷째의 운영 문서 줄, "번호와 느낌표"의 느낌표 기준·PR 서식의 칸·squash 제목을 직접 주지 않는 항목, "릴리스 워크플로"의 다시 돌린 릴리스 항목, "사람 몫" 전부, ADR 0020 Consequences "헌법"이다.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 시작할 때 agent-os의 변경을 본다. 이 티켓이 옮기는 글(`docs/constitution/operations.md`의 "릴리스 노트 조각"과 "판이 나는 차례와 실패한 판을 다시 돌리는 절차", `docs/constitution/tech.md`의 행, `.claude/skills/next-session/merge.md`의 판 내기를 기다리는 단계, `docs/agents/issue-tracker.md`와 `.claude/skills/implement/SKILL.md`의 해당 문장)이 `git -C C:/project/agent fetch origin` 뒤에 `b74a8adf2..origin/dev`에서 바뀌었으면 그 변경을 함께 옮길지 사용자에게 묻고 멈춘다(명세 "따르는 것과 옮기는 방식"의 확인을 이 티켓이 옮기는 파일에 친다). 받아 오기나 그 확인이 오류로 끝나면 빈 출력으로 보지 않고 그 오류를 보고하고 멈춘다. 사용자에게 물었으면 그 답과 본 agent-os 커밋을 Comments에 적는다. 기점이 `1aac0cf`가 아니라 `b74a8adf2`인 까닭은 명세 "따르는 것과 옮기는 방식"이 적는다.
- [x] 운영 문서의 두 절과 `tech.md`의 두 행, 그리고 운영 문서 8줄의 "버전 태그를 붙여 내는 것은 release-image다"를 새 절을 가리키게 고친 문장의 초안을 사용자에게 보이고 **멈춘다**. 헌법의 개정은 사용자가 승인한다(헌법 거버넌스). 승인을 받은 뒤 고치고, 승인을 `## Comments`에 사용자의 글 그대로 적는다. 절을 더하므로 헌법 판을 minor로 올린다(`docs/constitution/README.md`의 판 줄. 올린 까닭은 이 PR의 일지에 적는다). 판을 매기기 전에 `uv run python tools/sibling_overlap.py`로 형제 브랜치가 먼저 가져간 판을 본다.
- [x] 느낌표의 기준은 ADR 0020 "올릴 때 운영자가 손댈 것의 기준"이다. 운영자가 업그레이드할 때 손댈 것(설정, 환경 변수, 데이터, 플러그인 코드)이 있는 변경에 붙이고, 마이그레이션이 든 변경, 재색인이 필요해지는 변경, 계약의 판에서 앞자리를 올리는 변경은 언제나 붙인다. 보는 자리는 PR 서식의 칸, 노트 검사(05), 리뷰 봇(07)이다.
- [x] 릴리스가 나는 차례와 다시 돌리는 절차는 agent-os의 갈래를 모두 든다. 쓰기 전에 그 절의 문단을 하나씩 대 보고 빠진 갈래가 없는지 본다. 이 저장소에서 다른 것은 이미지가 둘이고, 시험 단계가 단독 compose 시험이며, 다시 돌린 릴리스가 앞 실행이 남긴 초안을 지운 뒤 새 초안을 만든다는 것이다(명세 "릴리스 워크플로"). 절이 적는 잡과 단계의 이름은 agent-os `release.yml`의 이름이고, 08이 워크플로를 옮긴 뒤 그 이름과 같은지 본다.
- [x] `merge.md`의 "출시 PR"과 핫픽스의 병합 뒤에 릴리스를 기다리는 단계를 더한다. 병합 커밋의 해시로 릴리스 워크플로의 실행을 찾아 끝까지 보고, 결과는 agent-os `merge.md`의 "판 내기를 기다린다" 절이 가르는 갈래를 모두 옮긴다. 갈래의 원천은 그 절이고, 릴리스했다, 제품 변경이 없어 릴리스 없이 성공했다, 더 나중 실행에 밀려 취소됐다, 실패했다는 그 가운데 몇이다(실행을 끝내 찾지 못한 경우도 그 절에 있다). 같은 절의 일지 기록 줄(병합 커밋의 해시와 실행 번호와 결과를 적는 줄)과 끊긴 세션이 그 줄로 이어받는 길, 출시 PR과 핫픽스에서 운영에서 개발로 합치기와 이 기다림의 차례도 이 저장소의 이름으로 함께 옮긴다. 이 단계는 방금 병합한 커밋(병합 뒤 main의 끝)에 릴리스 워크플로 파일이 있을 때만 한다고 적는다. 병합하기 전의 main을 보면, 그 워크플로를 처음 main에 싣는 출시 PR에서 기다리기를 건너뛰어 첫 릴리스를 놓친다(08이 그 첫 릴리스를 끝까지 지켜보라고 넘긴다). 08이 dev에 들어가고 출시 PR로 main에 오르기 전에는 병합 커밋에도 그 워크플로가 없어, 그 사이의 핫픽스를 병합한 세션이 오지 않을 실행을 기다리지 않는다.
- [x] `merge.md` "출시 PR"의 전제 확인에 사람 몫이 끝났는지 보는 줄을 더한다. GitHub 환경 `release`의 배포 브랜치가 main 하나인지, 그 안에 비밀 값 둘(`DOCKERHUB_TOKEN`, `RELEASE_GH_TOKEN`)과 변수 `DOCKERHUB_NAMESPACE`가 있는지를 `gh api`로 이름만 읽어 본다(값은 읽지 않는다). Docker Hub의 저장소 둘(`njh6803/rag-engine-server`, `njh6803/rag-engine-worker`)은 GitHub 밖이라 `gh api`로 볼 수 없으므로, 로그인 없이 읽는 Docker Hub의 저장소 조회로 있는지 보는 명령을 이 티켓이 정해 적는다. 접근 토큰 자체는 값을 볼 수 없어 비밀 값의 이름이 있는 것으로 갈음한다. 이 확인은 릴리스 워크플로가 dev에 있고 main에 아직 없는 첫 출시 PR에서 하고, 하나라도 없으면 출시 PR을 병합하지 않고 사용자에게 넘긴다. 같은 절의 "이 저장소에서는 아직 출시 PR을 열어 본 적이 없어"는 출시 PR 32와 62가 병합된 뒤로 사실이 아니므로 고친다.
- [x] `merge.md`의 병합 명령(`gh pr merge <번호> --squash --match-head-commit <HEAD>`) 곁에, 병합하는 쪽이 squash 제목을 직접 주지 않는 까닭을 적는다. 제목을 주면(`--subject`, 웹 화면에서 제목을 고치기) 설정과 상관없이 그 제목이 main에 남아, 검사를 지난 PR 제목의 느낌표가 빠질 수 있다(명세 "번호와 느낌표").
- [x] `docs/agents/issue-tracker.md`의 "끝 줄을 적는 때"에, 제품 변경을 담은 기능의 마지막 티켓을 닫는 커밋이 끝 줄과 함께 기능 단락(`docs/release-notes/features/<slug>.md`, 한 단락에 줄바꿈을 뺀 400자 이하)을 싣는다는 것을 더한다. `.claude/skills/implement/SKILL.md`에는 그 문장과, 느낌표를 붙이는 때와 업그레이드 원고를 싣는 것을 더한다. 스킬을 고치기 전에 Skill 도구로 `writing-for-agents`를 부른다.
- [x] 고친 규약의 옛 표현을 하네스 전체(`.claude/`, `docs/agents/`, `docs/constitution/`, `CLAUDE.md`)에서 grep해 살아 있는 문서의 잔존이 0인지 본다(작업 규약 4). `**끝:**`을 적으라고 지시하는 다른 자리(`CLAUDE.md` 지도 표의 기능 계획 행 같은 것)도 같이 본다.
- [x] 이 티켓은 스킬을 고치는 하네스 일이다. 고친 `implement`와 `next-session`을 새 세션에서 불러, 기능의 마지막 티켓을 닫을 때 기능 단락을 싣는다는 지시와 출시 PR 앞의 사람 몫 확인이 실리는지 보고 Comments에 적는다(작업 규약 3, `docs/constitution/operations.md` 환경 규약 상세).
- [x] `merge.md`의 "운영에서 개발로 합치기"에, 운영에서 개발로 합치기 PR의 CI에서 마이그레이션 head가 하나인지 보는 시험(05)이 빨개지면 할 일을 짐작하지 않고 멈추고 사용자에게 묻는다는 줄을 더한다. 그 PR은 머리가 main이라 합치는 리비전을 더할 자리가 없고, 푸는 길은 그 일이 처음 날 때 정한다(사용자가 2026-11-18에 고른 것, 명세 "번호와 느낌표"의 head 항목).
- [x] 05의 노트 검사가 막는 글에서 가리킬 운영 문서의 절 이름을 Comments에 적는다. 05는 이 티켓 뒤에 돌아 그 이름을 쓴다.
- [x] 검사 넷이 초록이다.

## Comments

- **agent-os 변경 확인.** `git -C C:/project/agent fetch origin`이 종료 0으로 끝난 뒤 `git -C C:/project/agent log --oneline b74a8adf2..origin/dev -- docs/constitution/operations.md docs/constitution/tech.md .claude/skills/next-session/merge.md docs/agents/issue-tracker.md .claude/skills/implement/SKILL.md`가 종료 0에 빈 출력이었다. 이 티켓이 옮기는 파일은 기점 뒤로 바뀌지 않아 사용자에게 묻지 않았다. 옮긴 원본은 `origin/dev`의 해당 파일이다.
- **헌법 승인.** 운영 문서 두 절, `tech.md` 두 행, 헌법 판 올림(1.3.8에서 1.4.0)의 초안을 질문 화면으로 보이고 승인을 물었다. 사용자의 답은 다음과 같다.

  > 승인한다

- **헌법 판.** 절을 더하므로 minor로 1.4.0이다. 판을 매기기 전에 `uv run python tools/sibling_overlap.py`가 낸 형제의 가장 높은 판이 1.3.9(워크트리 `glossary-ask-remaining-names`)여서 그보다 높게 골랐다. 올린 까닭은 이 PR의 일지에 적는다.
- **05가 쓸 절 이름.** 노트 검사가 막는 글에서 가리킬 운영 문서의 절은 `docs/constitution/operations.md`의 "릴리스 노트 원고"다. 그 안에서 느낌표를 붙이는 기준은 "느낌표의 기준", 기준을 보는 자리는 "보는 자리" 문단이다.
- **08이 확인할 것.** 운영 문서의 "릴리스가 나는 차례와 실패한 릴리스를 다시 돌리는 절차"가 적은 잡과 단계의 이름은 agent-os `release.yml`의 이름(`지난 판의 공개 릴리스 확인`, `이미 공개된 판` 등 `판`이 든 이름 포함)을 옮긴 것이다. 단 이 저장소의 시험 단계는 `단독 compose 시험`으로 썼고, 준비 단계는 이름을 못박지 않고 "파이썬 의존성과 임베딩 모델 폴더를 맞추는 단계"로 적었다. 08이 워크플로를 옮긴 뒤 이름이 같은지 보고 다르면 운영 문서를 고친다. 그 절의 `tools/release_ci.py`의 `repository`, `judge`, `verify-files`와 `tools/release.py`의 `PRODUCT_PATHS`, `tools/check_notes.py`는 아직 없는 파일이고 02, 05, 08이 들인다.
- **병합 절차에서 정한 것.** 릴리스 기다림은 병합 커밋에 `.github/workflows/release.yml`이 있을 때만 한다. `릴리스:` 줄은 핫픽스도 출시 PR도 병합한 PR의 코멘트에 적는다(일지는 병합 전에 푸시를 마쳐 병합 뒤에 적으면 커밋되지 않는다). 이어받기는 결정표 맨 위 줄이 맡는다. 사람 몫을 보는 `gh api` 응답의 모양은 GitHub REST 문서에서 읽은 것이고, 환경이 없을 때 404가 나는 것과 Docker Hub 조회가 기존 저장소(`njh6803/agent-os-runtime`)에서 200, 없는 저장소(`rag-engine-server`, `rag-engine-worker`)에서 404인 것만 손으로 봤다. 환경이 생긴 뒤 처음 칠 때 `--jq`가 맞는지 본다.
- **옛 표현 잔존.** `판 내기`, `판 태그`, `제품 판`, `릴리스 노트 조각`, `올릴 때 할 일`, `올릴 때 운영자`, `되돌려 합치`, `해시 태그`를 `CLAUDE.md`, `.claude/**/*.md`, `docs/agents`, `docs/constitution`, `GLOSSARY.md`에서 찾았다. 남은 것은 용어집의 피할 말 항목, 운영 문서 19줄의 옛 이름 설명, ADR 0020의 결정 이름을 따옴표로 인용한 자리(`올릴 때 운영자가 손댈 것의 기준`, agent-os ADR 0056 결정 `판 내기의 차례와 실패`) 뿐이다. `**끝:**`을 적으라고 지시하는 다른 자리를 같이 봤고, `CLAUDE.md` 지도 표의 기능 계획 행에 기능 단락을 더했다.
- **새 세션 확인.** 새 컨텍스트의 서브에이전트에게 `implement` 스킬, `next-session`의 `merge.md`와 `SKILL.md`를 Read로 열게 하고 질문 다섯으로 물었다. 답은 파일의 줄 번호와 함께 돌아왔다. 기능의 마지막 티켓을 닫는 커밋이 `**끝:**` 줄과 함께 기능 단락을 싣는다는 것(implement 13줄), 느낌표와 업그레이드 원고(같은 줄), 출시 PR 전제 확인이 넷이고 넷째가 사람 몫을 `gh api`와 Docker Hub 조회로 본다는 것(`merge.md` 68~76줄), 릴리스 실행 결과의 갈래 다섯(같은 파일 123~128줄), 결정표 출시 줄의 전제 확인에 사람 몫이 든 것(`SKILL.md` 52줄)이 모두 실렸다. `implement` 스킬은 `disable-model-invocation`이라 Skill 도구로는 부르지 못해 Read로 열었다. 위 줄 번호는 셀프 리뷰 반영 전의 것이다.
- **셀프 리뷰 반영.** 두 축이 Major 셋을 냈고 모두 고쳤다. `릴리스:` 줄은 핫픽스도 출시 PR도 병합한 PR의 코멘트에 적고, 이어받기는 `next-session/SKILL.md` 결정표의 맨 위 줄이 맡는다. 다시 돌린 실행은 `다시 돌림` 줄을 새로 달아 이어받는다. 판정과 근거는 이 PR의 일지 `docs/journal/2026-11-19-0123-release-docs-and-merge-procedure.md`다.
- **08이 더 확인할 것.** 운영 문서의 단계 목록은 `체크아웃`, `빌더 준비`, `이미 공개된 판`까지 agent-os `release.yml`의 이름을 옮겼다. "이 저장소에서 agent-os와 다른 것"에 티켓이 적으라던 "다시 돌린 실행은 앞 초안을 지운다"는 agent-os의 `release.yml`에 이미 `앞 실행의 초안 지우기` 단계가 있어 거짓이라 뺐다. ADR 0020 "agent-os가 미룬 결정 셋"이 지금의 agent-os와 맞는지는 이 티켓이 보지 않았다.
