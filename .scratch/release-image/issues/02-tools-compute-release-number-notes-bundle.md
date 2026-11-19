# 02: 도구가 다음 릴리스 번호와 릴리스 노트와 배포 파일 묶음을 짓는다

**What to build:** 릴리스 워크플로(08)가 부를 도구가 `tools/`에 선다. agent-os 커밋 `1aac0cf`의 `tools/release.py`와 그 시험 `tests/tools/test_release.py`를 복사해 이 저장소의 값으로 고친 것이다. 하는 일은 넷이다.

- **번호.** git 이력과 버전 태그(git 태그 `v<번호>`)와 릴리스 설정 파일(`deploy/release.toml`)을 읽어, 릴리스할지와 다음 번호와 지난 릴리스로 고른 태그를 낸다.
- **노트.** 범위 안 커밋의 제목, 릴리스 노트 원고(`docs/release-notes/` 아래 `features/`, `upgrade/`, `intro/`), 이미지마다의 취약점 점검 결과, 서버 이미지의 `rag-engine --version`이 찍은 계약의 판 줄을 받아 릴리스 노트의 글을 낸다.
- **묶음.** `deploy/standalone/`의 파일에 번호와 이미지 이름공간을 채워 배포 파일 묶음(릴리스마다 이미지와 함께 내는 설치용 파일의 묶음) `rag-engine-<번호>.tar.gz`를 짓는다.
- **번호 태그 판정.** 이미지에 번호 태그를 붙일지 그대로 둘지 거부할지 붙이지 않을지를, 조회의 출력과 종료 코드와 올린 digest로 가르는 순수 함수다.

개발 세션이 릴리스의 때와 번호를 손으로 정하지 않게 하고(스토리 41), 업그레이드할 때 할 일과 계약의 판이 노트에 빠지지 않게 하며(스토리 31, 33, 34), 운영자가 받을 묶음을 첫 릴리스 전에 시험으로 짓게 한다(스토리 3, 4).

이 티켓이 묶음까지 맡는 것은 명세 "티켓을 나눌 때 함께 둘 것"의 둘째 묶음이다. agent-os에서 묶음을 짓는 함수는 번호와 노트와 같은 파일에 있고, 단독 compose 시험(03)이 그 함수로 묶음을 짓는다. 묶음만 다른 티켓이 옮기면 나란히 도는 두 티켓이 같은 파일을 새로 만들고, 시험이 앞 티켓보다 먼저 서게 된다. 처음 명세는 묶음 도구를 설치 안내와 한 묶음에 두었는데, 명세 검토가 그 차례 모순을 짚어 티켓을 나눈 세션이 명세를 고쳤다(일지 `docs/journal/2026-11-18-2135-release-image-tickets.md`).

근거는 명세 "따르는 것과 옮기는 방식", "제품 변경의 경로", "번호와 느낌표"의 번호와 `candidate_for` 항목, "단독 compose"의 `.env.example` 표지 항목, "배포 파일 묶음", "릴리스 노트", Testing Decisions의 도구 시험 항목이다.

**Blocked by:** 06 (헌법을 바꾸는 티켓은 그 기능의 첫 티켓이며 다른 티켓을 막는다. `docs/agents/issue-tracker.md`의 티켓 규약이고, 사용자가 2026-11-18에 이 차례를 골랐다)

**Status:** done

- [x] 시작할 때 agent-os의 변경을 본다. `git -C C:/project/agent fetch origin` 뒤에 `git -C C:/project/agent log b74a8adf2..origin/dev -- .github/workflows/release.yml tools/release.py tools/release_ci.py tools/check_notes.py deploy/ tests/tools/test_release.py tests/tools/test_release_ci.py tests/tools/test_release_workflow.py tests/tools/test_check_notes.py tests/tools/test_deploy_guide.py`가 비지 않으면 그 변경을 함께 옮길지 사용자에게 묻고 멈춘다(명세 "따르는 것과 옮기는 방식"). 두 명령 가운데 하나라도 오류로 끝나면 빈 출력으로 보지 않고 그 오류를 보고하고 멈춘다. 바뀐 파일이 이 티켓이 옮기는 파일이 아니면 묻지 않고 그 커밋을 Comments에 적고 잇는다. 사용자에게 물었으면 그 답과 본 agent-os 커밋을 Comments에 적는다. 기점이 `1aac0cf`가 아니라 `b74a8adf2`인 까닭은 명세 "따르는 것과 옮기는 방식"이 적는다.
- [x] 제품 변경(릴리스에 실릴 변경으로 세는 경로를 고친 변경)의 경로는 `src/`, `pyproject.toml`, `uv.lock`, `deploy/` 넷이고 한 자리에 둔다. 05의 노트 검사가 같은 목록을 가져다 쓴다. `README.md`, `docs/`, `compose.test.yml`, `compose.eval.yml`, 릴리스 노트 원고는 세지 않는다. 시험은 `pyproject.toml`만 고친 커밋이 제품 변경으로 세어지는 것과, `compose.test.yml`만 고친 커밋과 `README.md`만 고친 커밋이 세어지지 않는 것을 본다(명세 "제품 변경의 경로").
- [x] 번호의 규칙은 agent-os ADR 0056 결정 "번호"와 그 도구 그대로다. 첫 릴리스는 `0.1.0-rc.1`이고, 릴리스 설정 파일에 `candidate_for = "0.1.0"`이 있는 동안 끝의 `-rc.N`만 오른다. 번호는 이 저장소의 태그와 제목에서만 센다. 제목은 커밋 검사(`tools/check_commit_msg.py`)의 `PATTERN`으로만 읽는다. 이 저장소의 `PATTERN`과 `PASS_PREFIXES`가 agent-os의 것과 같은 꼴인지 먼저 견주고, 다르면 시험 사례를 이 저장소의 꼴로 고친다.
- [x] 노트의 절 차례는 경고, 소개, 기능 소개, 업그레이드할 때 할 일, 계약의 판, 새 기능, 고친 것, 그 밖의 변경이다. agent-os의 "올릴 때 할 일"을 이 저장소에서는 "업그레이드할 때 할 일"로 부른다(용어집이 그 일의 이름을 업그레이드로 바꿨다). "계약의 판" 절은 도구가 인자로 받은 줄(01이 정한 `--version`의 둘째 줄부터)을 그대로 싣는다. 인자의 꼴은 이 티켓이 정해 도구의 독스트링에 적고, 08이 그 꼴로 부른다. 그 줄을 받지 못하면 노트를 짓지 않고 실패한다. 계약의 판이 빠진 노트가 나가면 운영자가 클라이언트와 맞는지 알 길이 없다(명세 "릴리스 노트").
- [x] 묶음의 틀에는 자리 표지 둘, `@RAG_ENGINE_NAMESPACE@`와 `@RAG_ENGINE_VERSION@`을 쓴다(명세 "단독 compose"의 `.env.example` 항목). `@RAG_ENGINE_`으로 시작하는 다른 표지가 남으면 묶음을 짓지 않는다. 묶음은 풀면 `rag-engine-<번호>/` 하나가 나오고, 같은 입력이면 바이트가 같다. agent-os의 도구처럼 틀의 빈 하위 폴더는 담지 않는다(그래서 설치 안내가 `models/embedding/`을 만드는 명령을 적는다. 명세 "단독 compose"). 이 티켓의 시험은 임시 폴더의 틀로 묶음을 짓고 풀어 본다. `deploy/standalone/`은 03이 만든다.
- [x] 도구는 agent-os와 같이 표준 라이브러리만 쓴다. 의존성을 깔지 않은 CI 잡에서 `python3`로 돌기 때문이다(`ci.yml`의 `ticket` 잡이 커밋 검사를 그렇게 부른다). 개발 PC에서는 `uv run python`으로 친다(`CLAUDE.md` 환경 함정). 도구가 부르는 외부 명령(git)에는 호출마다 시간 제한을 둔다(`.claude/rules/tools.md`, `tools/check_instructions.py`의 `calls_without_timeout`).
- [x] 실패하는 시험을 먼저 쓴다. 임시 git 저장소에 커밋과 태그를 만들어 넣는다(선례 `tests/tools/test_check_ticket.py`. 임시 디렉터리의 git은 `.claude/rules/tools.md`의 `REPO_LOCATION_VARS` 항목을 따른다). agent-os의 사례를 모두 옮기고, 셋을 더한다. `pyproject.toml`만 고친 변경, "계약의 판" 절(줄이 그대로 실리는 것과 줄이 없을 때의 실패), 도구가 낸 묶음 이름이 `rag-engine-<번호>.tar.gz`인 것이다.
- [x] 옮긴 도구의 출력 문구와 독스트링은 이 저장소의 이름(릴리스, 정식 릴리스, 버전 태그, 릴리스 노트 원고, GitHub 릴리스)으로 쓴다(명세 "따르는 것과 옮기는 방식"). 옛 이름("판 내기", "판 태그", "노트 조각")을 그 두 파일에서 grep해 0인지 본다.
- [x] 검사 넷이 초록이다.

## Comments

### 2026-11-19 구현 세션이 남긴 확인

- **agent-os 변경 확인.** `git -C C:/project/agent fetch origin`이 종료 0으로 끝났고, 이어 `git -C C:/project/agent log --oneline b74a8adf2..origin/dev -- <티켓이 적은 경로 열 개>`도 종료 0에 출력이 비었다(agent-os origin/dev는 `148c86d`). 옮길 변경이 없어 사용자에게 묻지 않았다.
- **커밋 검사의 `PATTERN`.** agent-os `1aac0cf`의 `tools/check_commit_msg.py`와 이 저장소의 것을 `diff`로 견주니 차이가 없었다(`PATTERN`과 `PASS_PREFIXES`가 같다). 그래서 시험 사례의 제목 꼴은 고치지 않았다.
- **08이 부를 꼴(`notes`의 계약의 판 인자).** `python3 tools/release.py notes --number <번호> --contract-versions <파일> [--grype 이미지=경로]... [--repo DIR] [--head REV]`. `<파일>`에는 서버 이미지에서 `rag-engine --version`을 돌려 첫 줄(`rag-engine <번호>`)을 뺀 둘째 줄부터를 그대로 담는다(01이 찍는 네 줄은 `검색 도구의 형식 …`, `수집 API와 관리 API의 경로 …`, `파서 인터페이스 …`, `색인 형식의 스키마 …`이다). 도구는 그 줄을 고치지 않고 `## 계약의 판` 절의 `text` 코드 울타리 안에 싣는다. 줄바꿈이 노트에서 접히지 않게 하려는 것이다. 인자가 없거나 파일을 읽지 못하거나 글자가 든 줄이 하나도 없거나 코드 울타리가 든 줄이 있으면 노트를 짓지 않고 종료 1로 끝난다. 이 꼴의 원천은 도구의 독스트링이다.
- **agent-os와 다른 것.** ① `PRODUCT_PATHS`가 `("src", "pyproject.toml", "uv.lock", "deploy")`다. ② 자리 표지가 `@RAG_ENGINE_VERSION@`, `@RAG_ENGINE_NAMESPACE@`이고 묶음 이름이 `rag-engine-<번호>.tar.gz`다. ③ 노트 절 이름 "올릴 때 할 일"이 "업그레이드할 때 할 일"이고, 그 다음에 "계약의 판" 절이 선다. ④ `render_notes`가 `contract` 인자를 필수로 받고, 절이 하나도 없을 때 빈 글을 내던 갈래는 계약의 판 절이 늘 서므로 없어졌다. ⑤ Grype 경고의 "고친 판은"을 "고친 번호는"으로 바꿨다(판은 계약의 번호를 가리키는 말이라서다). 그 밖의 번호 규칙, 커밋 고르기, 묶음 짓기, 번호 태그 판정은 원본 그대로다.
- **독스트링의 근거.** 원본 독스트링이 기대던 agent-os의 프로브(`release_mechanics` README)와 일지는 이 저장소에 없다. 그 문장들은 agent-os가 적어 둔 것을 옮겼고 이 저장소에서는 다시 재지 않았다는 뜻으로 고쳐 적었다. 시험 머리 주석과 `EXISTING` 주석의 `docker buildx imagetools inspect` 출력 꼴도 같다.
- **빨강을 본 시험.** 시험 파일을 먼저 쓰고 `tools/release.py`를 들이기 전에는 `tools.release`를 불러오지 못해 파일 전체가 수집 오류였다. 구현 뒤 `uv run pytest tests/tools/test_release.py`는 104개가 통과했고, 셀프 리뷰를 반영한 뒤에는 109개가 통과했다.
- **옛 이름 잔존.** 두 파일(`tools/release.py`, `tests/tools/test_release.py`)에서 "판 내기", "판 태그", "노트 조각", "조각", "올릴 때", "정식 판", "지난 판", "판 번호", "제품 판", `AGENT_OS`, `agent-os-`, `agentos`를 grep해 0이었다. "판"은 계약의 판과 "판정"에만 남았다.
- **헌법 문서.** 06 일지 "다음"의 첫째 몫대로 `docs/constitution/operations.md`의 제품 변경 경로 목록을 `tools/release.py`의 `PRODUCT_PATHS`를 가리키는 한 줄로 줄였다. 사용자가 이 초안을 승인했다(승인은 판 1.5.1을 말했으나 그 사이 dev가 1.5.1을 가져가 1.5.2로 올렸다. 문구만 고친 patch다).
