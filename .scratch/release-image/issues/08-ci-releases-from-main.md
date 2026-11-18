# 08: main이 움직이면 CI가 번호를 계산해 이미지 둘과 GitHub 릴리스를 낸다

**What to build:** main에 푸시가 오면(출시 PR이나 핫픽스 PR이 병합되면) 새 릴리스 워크플로가 돈다. 지난 릴리스 뒤로 제품 변경이 없으면 성공으로 끝난다. 있으면 첫째 잡이 02의 도구로 번호와 노트를 계산하고, 01의 bake 설정으로 이미지 둘을 짓고, 그 이미지로 03의 단독 compose 시험을 돌리고, 취약점을 점검한 뒤 Docker Hub에 커밋 태그로 올리고, 시험한 이미지와 올린 이미지가 같은지 견준다. 둘째 잡이 번호 태그를 붙이고 GitHub 릴리스(GitHub에 올리는 게시물)를 만들고 버전 태그를 단다. GitHub 릴리스에는 배포 파일 묶음, 릴리스 노트, 이미지마다의 소프트웨어 목록(SBOM)과 점검 결과가 붙는다(스토리 1, 2, 35, 36, 41, 42, 51, 54).

이 티켓이 release-image의 마지막 티켓이다. 릴리스 워크플로와 릴리스 설정 파일 `deploy/release.toml`(`candidate_for = "0.1.0"`)을 함께 싣고, 이 기능의 기능 단락과 첫 정식 릴리스의 소개 글, 기능 계획의 `**끝:**` 줄도 함께 싣는다. 워크플로가 설치 안내와 묶음보다 먼저 main에 닿지 않게 하고, 첫 릴리스가 나는 병합을 하나로 정하려는 것이다(명세 "티켓을 나눌 때 함께 둘 것").

agent-os 커밋 `1aac0cf`의 `.github/workflows/release.yml`, `tools/release_ci.py`와 그 시험, `tests/tools/test_release_workflow.py`를 옮겨 이 저장소의 값(이미지 둘, 이미지 이름, 묶음 이름, 시험 단계)으로 고친다. node, pnpm, Playwright 단계는 옮기지 않는다.

근거는 명세 "릴리스 워크플로" 전부, "이미지와 계정"의 태그 항목, "번호와 느낌표"의 `candidate_for` 항목, "릴리스 노트"의 "계약의 판" 절과 첫 릴리스 항목, "ci.yml"의 82줄 주석 항목, "사람 몫", "티켓을 나눌 때 함께 둘 것", Testing Decisions의 도구 시험·저장소 상태 시험·워크플로에 자동 시험이 없다는 항목·수락 항목, Further Notes의 첫 릴리스에서 지켜볼 것이다.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07

**Status:** ready-for-agent

### 워크플로

- [ ] 시작할 때 agent-os의 변경을 본다. `git -C C:/project/agent fetch origin` 뒤에 `git -C C:/project/agent log b74a8adf2..origin/dev -- .github/workflows/release.yml tools/release.py tools/release_ci.py tools/check_notes.py deploy/ tests/tools/test_release.py tests/tools/test_release_ci.py tests/tools/test_release_workflow.py tests/tools/test_check_notes.py tests/tools/test_deploy_guide.py`가 비지 않으면 그 변경을 함께 옮길지 사용자에게 묻고 멈춘다(명세 "따르는 것과 옮기는 방식"). 두 명령 가운데 하나라도 오류로 끝나면 빈 출력으로 보지 않고 그 오류를 보고하고 멈춘다. 바뀐 파일이 이 티켓이 옮기는 파일이 아니면 묻지 않고 그 커밋을 Comments에 적고 잇는다. 사용자에게 물었으면 그 답과 본 agent-os 커밋을 Comments에 적는다. 기점이 `1aac0cf`가 아니라 `b74a8adf2`인 까닭은 명세 "따르는 것과 옮기는 방식"이 적는다.
- [ ] 워크플로는 main 푸시에서만 돈다. 수동 실행 계기는 두지 않고, 실패한 릴리스는 실패한 잡을 다시 돌려 잇는다. 잡은 둘이고 둘 다 GitHub 환경 `release`를 쓴다. 시험과 점검을 모두 마친 뒤에 Docker Hub에 로그인한다(시험이 도는 동안 러너에 자격 파일이 없다).
- [ ] 첫째 잡의 시험 단계는 방금 지어 러너에 실은 이미지 둘과 02의 도구로 지은 묶음으로 03의 단독 compose 시험을 경로를 주어 돌린다. 이미지와 묶음과 모델 폴더는 03이 정한 환경 변수로 넘긴다. 모델 폴더는 `eval-fast` 잡과 같은 캐시 키로 복원만 하고(저장은 `eval-fast`가 맡는다), 캐시가 없으면 임베딩 서버의 첫 시작이 내려받는다. 복원한 뒤에는 캐시가 있든 없든 그 폴더를 만들어 uid 10001에게 주고 넘긴다(명세 "릴리스 워크플로"의 시험 단계 항목, 03의 CI 항목과 같다).
- [ ] 노트의 "계약의 판" 절은 지은 서버 이미지에서 `rag-engine --version`을 설정 없이 돌려 둘째 줄부터를 02의 도구에 넘긴다(01이 설정 없이 돌게 했다).
- [ ] 올린 뒤 시험한 이미지와 올린 이미지를 이미지 설정 파일의 해시로 견준다. 시험한 쪽은 점검을 위해 `docker save`로 받은 파일에서, 올린 쪽은 커밋 태그로 레지스트리에 물은 linux/amd64 매니페스트의 `config.digest`에서 읽고, 다르면 번호 태그와 GitHub 릴리스 앞에서 실패한다(명세 "릴리스 워크플로"의 대조 항목, agent-os `release.yml`의 "시험한 이미지와 올린 이미지 대조" 단계).
- [ ] 취약점 점검은 Grype 0.121.3과 Syft 1.57.1을 digest로 고정해 쓰고, 이미지 둘마다 소프트웨어 목록과 점검 결과를 GitHub 릴리스에 붙인다. 막는 기준은 agent-os와 같다. 바깥 이미지(nginx, PostgreSQL, TEI)는 점검하지 않는다.
- [ ] 이미지 태그는 번호 태그와 커밋 태그 `sha-<커밋 해시 40자>` 둘이고 `latest`는 두지 않는다. 출시 후보의 GitHub 릴리스에도 GitHub 릴리스의 `prerelease` 칸(GitHub가 정식이 아닌 게시물에 붙이는 표시)을 켜지 않는다. 다시 돌린 릴리스는 앞 실행이 남긴 초안을 지운 뒤 새 초안을 만든다.
- [ ] 쓰는 액션은 이 티켓을 할 때의 판을 커밋 해시로 고정한다(이 저장소 `ci.yml`의 고정 꼴). 첫째 잡의 제한 시간은 캐시가 없는 경우(이미지 짓기, 모델 내려받기, 1800초까지의 기다림, 점검, 올리기)를 넘게 잡고 그 셈을 잡 옆 주석에 적는다(명세 Testing Decisions). agent-os의 짓는 잡 30분을 옮기지 않는다. 둘째 잡은 어림으로 시작한다(`ci.yml` 머리 주석의 관례). 워크플로의 보안 약점을 찾는 감사 도구(zizmor)를 지난다.
- [ ] 06이 운영 문서에 적은 릴리스의 차례와 다시 돌리는 절차가 이 워크플로의 잡과 단계 이름과 같은지 grep으로 대 보고, 다르면 같은 PR에서 그 문서를 맞춘다. 헌법의 문구를 고치면 판을 patch로 올리고 사용자 승인을 받는다.

### 판정 도구와 시험

- [ ] 워크플로가 부르는 판정 도구(이미지 설정 파일의 해시 읽기, 매니페스트 고르기, 사전 확인, 받은 파일 대조, 번호 태그 판정의 명령줄)와 그 시험을 옮긴다. 이미지는 agent-os의 넷이 아니라 둘이다.
- [ ] 저장소 상태 시험을 옮긴다. bake 설정의 저장소 이름이 단독 compose의 `image:` 줄과 설치 안내의 대응표와 같은지 본다. agent-os의 시험이 견주는 e2e의 compose 파일(`compose.fixtures.yaml`)은 이 저장소에 없으므로(단독 compose 시험이 묶음의 compose를 그대로 쓴다) 그 견줌은 빼고 뺀 까닭을 시험의 독스트링에 적는다. 이 저장소에서 더하는 것은 둘이다. 이미지를 짓는 파일의 `FROM`과 compose의 바깥 이미지 줄이 digest(`@sha256:`)로 고정됐는지(스토리 53), 프록시 설정의 `/mcp` 자리가 `proxy_buffering off`를 두는지다(스토리 40). 지금의 서버는 응답을 모으지 않게 하는 머리를 싣기 때문에 기능 시험으로는 그 설정의 유무가 갈리지 않는다(명세 Testing Decisions의 저장소 상태 시험 항목). 두 판정이 일부러 깨뜨린 사본에서 빨개지는 것을 손으로 보고 Comments에 적는다.
- [ ] 릴리스 워크플로 파일의 꼴을 보는 시험(`test_release_workflow.py`)을 옮겨 이 저장소의 잡과 단계로 고친다. 워크플로 자체의 자동 시험은 없다(명세 Testing Decisions).
- [ ] 실패하는 시험을 먼저 쓴다. 검사 넷이 초록이다.

### 설정 파일, 원고, 끝 줄

- [ ] `deploy/release.toml`을 `candidate_for = "0.1.0"` 한 칸으로 만든다.
- [ ] `docs/release-notes/features/release-image.md`를 운영자의 말로 쓴 한 단락(줄바꿈을 뺀 400자 이하, 파일 경로·ADR 번호·티켓 이름 없음)으로 쓰고, `docs/release-notes/intro/0.1.0.md`를 첫 릴리스에 함께 실리는 core와 search-eval을 설명하는 글로 쓴다(명세 "릴리스 노트"의 첫 릴리스 항목). 05의 노트 검사 (나)(다)를 지난다.
- [ ] `ci.yml` `image` 잡의 머리 주석("버전 태그를 붙여 내는 것은 release-image"류)을 릴리스 워크플로를 가리키게 고친다.
- [ ] 기능 계획 `.scratch/release-image/plan.md`에 `**끝:**` 줄을 더하고 `uv run python tools/plan_table.py`를 돌려 같은 커밋에 싣는다.
- [ ] `deploy/`를 고쳤으므로 단독 compose 시험을 개발 PC에서 경로를 주어 한 번 더 돌리고 결과를 Comments에 적는다.

### 사람 몫과 넘길 것

- [ ] 명세 "사람 몫"을 한 화면으로 사용자에게 보인다. Docker Hub의 저장소 둘과 접근 토큰, 배포 브랜치를 main 하나로 좁힌 GitHub 환경 `release`, 그 안의 비밀 값 둘(`DOCKERHUB_TOKEN`, `RELEASE_GH_TOKEN`)과 변수 `DOCKERHUB_NAMESPACE`다. `RELEASE_GH_TOKEN`은 이 저장소 하나에 Contents와 Workflows의 읽기·쓰기만 준 세분 토큰이고, 이름과 권한을 미리 채운 만들기 주소(GitHub 문서가 적는 템플릿 주소)를 함께 보인다. 비밀 값은 사용자가 직접 넣고 세션에 넘기지 않는다. 보인 화면을 일지에 적는다.
- [ ] 이 티켓의 PR을 병합한 세션은 출시 PR의 계기가 서므로, 다음 지시문에 출시 PR 세션이 할 일을 넘긴다. 병합 전에 06이 `merge.md`에 더한 사람 몫 확인, 출시 PR에서 `ci.yml`의 단독 compose 시험 잡이 GitHub 러너에서 초록인지(수락의 첫째. 리눅스에서의 첫 확인이다), 병합 뒤 첫 릴리스를 끝까지 지켜보고 Further Notes의 셋(eval 캐시를 읽는지, 두 이미지의 층이 한 벌로 저장되는지, "계약의 판" 절이 `--version`의 줄과 같은지)을 일지에 적는 것, 그리고 GitHub 릴리스에서 받은 묶음과 Docker Hub에서 받은 이미지(이름공간 `njh6803`과 그 번호)로 단독 compose 시험을 개발 PC에서 한 번 더 치는 것(수락의 둘째)이다. 그때 이미지는 빈 설정 폴더(`DOCKER_CONFIG`를 빈 임시 폴더로 준다)로 받아, 로그인 없이 받히는 것(스토리 2)을 함께 보인다.
