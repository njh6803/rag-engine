# glossary-release-number-names: 릴리스 노트의 "계약의 판" 절과 릴리스 번호를 가리키는 "판"을 "계약 버전"과 "릴리스", "버전"으로 바꾼다 · 2026-11-20

PR 79(일지 `2026-11-19-2318-glossary-contract-version-review-bot.md`)를 병합한 같은 세션이 그 일지 "다음"의 남은 영역을 이어서 한 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-release-number-names.md`, 브랜치는 `chore/glossary-release-number-names`이고 `origin/dev`(`3cd84f5`, PR 83까지 든 판)에서 새로 땄다. 용어집의 이름을 agent-os의 결정에 맞추는 일의 아홉째 PR이다. 계기, 한 것, 훑은 것, 검증을 차례로 두고, 셀프 리뷰 이후의 절은 PR을 연 뒤 이어 쓴다.

## 계기

PR 79 보고의 끝에서 사용자에게 "남은 판 영역 가운데 릴리스 번호의 판을 이 세션에서 이어 낼까요?"를 물었고 "네, 이어서"라고 답했다. 이 영역은 릴리스 노트의 절 이름과 `tools/release.py`를 건드리는데, 그 파일들을 같은 때 바꾸던 PR 80과 PR 83이 열려 있었다. "PR 80 병합을 기다리지 않고 겹치지 않는 부분부터 먼저 낼까요?"를 물었더니 "병합 뒤에 시작"이라고 답해, 두 PR이 병합된 뒤(`3cd84f5`)에 시작했다. 요청 범위는 PR과 병합까지다.

시작해 보니 `release-image` 기능이 같은 날(2026-11-20) PR 83으로 마지막 티켓(08)을 닫아 기능 계획에 `끝:` 줄이 서 있었다. PR 78과 PR 79의 티켓은 이 영역이 `.scratch/release-image/`의 명세와 티켓도 맞추도록 맡겼으나, 그 글은 이제 끝난 기능의 기록이 되어 `core`·`search-eval`처럼 고치지 않고 ADR 0020의 이력이 새 이름을 알리게 했다(티켓의 "이번에 바꾸지 않는 것").

## 한 것

- 릴리스 노트의 절 이름 "계약의 판"을 "계약 버전"으로 바꿨다. `tools/release.py`(독스트링, 오류 문구, 도움말, 노트가 찍는 제목 `## 계약 버전`) 10곳, 그 시험 `tests/tools/test_release.py`의 문구 6곳과 이름 7곳(시험 이름 여섯과 시험이 만드는 임시 파일 이름 `계약_버전.txt`), `tests/tools/test_release_workflow.py`의 시험 이름 하나, `release.yml` 주석, `src/rag_engine/main.py` 주석.
- "API 문서의 판 칸", "MCP 서버 정보의 판"을 "버전 칸", "버전"으로 바꿨다(`release_number.py` 독스트링, `tests/server/test_release_number.py`의 독스트링과 시험 이름 둘). 칸의 실제 이름이 `version`이다. 용어집이 계약과 헌법의 번호를 "버전"으로, 서버에 붙이는 번호를 "릴리스"로 가르므로, 번호의 자리를 부르는 말에는 칸 이름 그대로 "버전 칸"을 썼다.
- 릴리스 워크플로의 단계 이름 셋을 바꿨다. `지난 판의 공개 릴리스 확인`은 `지난 릴리스의 GitHub 릴리스 확인`, `판 없음 알림`은 `릴리스 없음 알림`, `이미 공개된 판`은 `이미 공개된 릴리스`다. 이 이름은 `gh run view --json jobs`의 `steps[].name`으로 읽히므로 운영 문서의 표와 설명(47, 48, 60, 80행)을 함께 맞췄다. 단계 이름을 글자로 맞대는 시험은 없었다(`git grep`으로 `tools`, `tests`, `.github`, `deploy`, `src`를 훑었다).
- `tools/release_ci.py` 오류 문구 "번호 태그를 붙인 판일 수 있어"를 "릴리스일 수 있어"로, `tests/tools/test_release_ci.py`의 시험 이름 `…_파일의_판_번호가…`를 `…_파일의_릴리스_번호가…`로 바꿨다.
- PR 80이 PR 78 뒤에 새로 써서 다시 들여온 계약 번호 판 둘을 바꿨다(`.github/PULL_REQUEST_TEMPLATE.md` 36행, `tools/check_notes.py` 84행의 독스트링).
- 루트 `README.md`의 "## 판"을 "## 릴리스 번호"로, "이 서버의 판은 semver다"를 "이 서버의 릴리스 번호는 semver다"로, "첫 공개 판 0.1"을 "첫 릴리스 0.1"로 바꿨다(용어집에 "공개 릴리스"라는 말이 없어 처음 쓴 "첫 공개 릴리스"를 셀프 리뷰 뒤 고쳤다). 첫 릴리스 소개문 `docs/release-notes/intro/0.1.0.md` 1행의 "첫 공개 판"은 "첫 정식 릴리스"로 바꿨다(출시 후보 `0.1.0-rc.N`도 같은 소개를 싣지만 0.1.0은 정식 릴리스다). 시작하지 않은 계획 `.scratch/diag-bundle/plan.md`의 판 셋은 "릴리스 번호와 계약 버전"과 "버전"으로, 그 제목이 생성 표 `.scratch/plan.md`의 `diag-bundle` 행에 실려 `tools/plan_table.py`로 다시 만들었다.
- 헌법 `docs/constitution/operations.md`(사용자 승인): 31행 노트 절 차례와 절 이름 "계약의 판" 둘을 "계약 버전"으로, 80행을 이 문서와 `release.yml`의 단계 이름 셋이 agent-os의 이름에서 `판`을 용어집의 `릴리스`로 바꾼 것이라는 말로 바꿨다. 헌법 버전을 1.5.5에서 1.5.6(patch)으로 올렸고(`docs/constitution/README.md`), ADR 0016 이력에 까닭을, ADR 0020 이력에 바뀐 이름을 적었다. 본문에 포인터를 달지 않은 까닭은 본문이 단계 이름과 절 이름을 적지 않았고 앞 이력(2026-11-19)이 이미 "계약의 판은 계약 버전으로 읽는다"고 적었기 때문이다.
- 사용자 승인: 선택 화면 두 개를 한 번에 보였다. 헌법 문구와 버전 올림은 "바꾼다", 단계 이름은 "릴리스로 바꾼다"(둘 다 권고)를 골랐다. 원문은 티켓의 `## Comments`에 있다.

## 훑은 것

PR 79 일지가 정한 모양(일치 지점의 앞뒤 글자, UTF-8, 양성 대조)을 지켰고, 이번에는 릴리스 낱말 필터를 쓰지 않았다. 처음 훑을 때 필터가 `## 계약의 판` 같은 줄을 떨어뜨려 양성 대조가 0으로 나와 필터를 걷고 슬라이스를 고쳤다(이름 바꾸기를 훑을 때 필터와 양성 대조가 한 번 더 일을 했다).

- 바꾸기 전: 릴리스 영역 파일 14개와 헌법 문서 넷, 명세·계획을 앞뒤 30자와 함께 찍었다(`sweep_pan.py`와 `sweep_release.py --all`, 스크래치패드 스크립트). 양성 대조로 `tools/release.py`의 "계약의 판" 열 자리가 나왔다.
- 바꾼 뒤: 바꾼 파일 16개를 같은 방식으로 찍으니 25곳이 남았고 모두 바꾸지 않기로 한 것이다. 색인 판 계열(PR 서식 35행, README 59·60·67행의 색인 판 요소, alembic 판, `operations.md` 38행), 액션·점검 도구·Docker 엔진·이미지의 판(`release.yml` 22, 23, 45, 46, 154행, `test_release_workflow.py` 47, 79행, `release_ci.py` 33, 101행, `test_release_ci.py` 5행, README 78행의 "이미지 판"), agent-os 결정 이름 인용(`release.yml` 442행, `operations.md` 31, 66, 75행), 그리고 새로 쓴 `operations.md` 80행이 옛 말 `판`을 따옴표로 가리킨 것이다. 새 이름 "계약 버전"은 `tools/release.py`에서 10곳으로 세어 양성 대조가 맞았다.
- 잔존: 살아 있는 글(일지, 대기열, ADR 본문과 이력, 끝난 기능과 티켓의 기록, 입력 글 제외)에서 `계약의 판|계약의_판|지난 판의 공개|판 없음 알림|이미 공개된 판|API 문서의 판|API_문서의_판|서버_정보의_판`을 `git grep`으로 찾으니 ADR 0016·0020의 본문과 이력만 남았다. 모두 옛 이름을 설명하거나 새 이름으로 읽게 하는 글이다.
- 시험 이름이나 문구를 맞대는 곳: 변이 표, 프로브 toml, 문서가 옛 시험 이름 `계약의_판`을 적었는지 `git grep`으로 찾았으나 `tests/tools/test_release.py`와 `test_release_workflow.py` 밖에는 없었다.

## 검증

손으로 친 것은 파이프 없이 하나씩 쳤다.

- 영향을 받는 시험: `tests/tools/test_release.py`, `test_release_workflow.py`, `test_release_ci.py`, `tests/tools/test_check_notes.py` 345건 통과. `tests/server/test_release_number.py`는 테스트 PostgreSQL이 없어 2건이 환경 오류였고(`RAG_TEST_DATABASE_URL`이 없다. skip이 아니라 실패다), `docker compose -f compose.test.yml up -d --wait`로 띄우고 값을 준 뒤 2건 통과.
- `uv run ruff check .` 통과, `uv run ruff format --check .` 792개 파일 이미 맞음, `uv run pyright` 0 errors, `uv run lint-imports` 2 kept 0 broken, `uv run python tools/check_instructions.py` 출력 없음.
- `uv run python tools/plan_table.py --check`는 처음에 실패했다(`diag-bundle` 제목이 바뀌었는데 생성 표가 그대로였다). `uv run python tools/plan_table.py`로 다시 만들었고 달라진 것은 그 행 하나다.
- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 이 브랜치의 새 번호는 헌법 1.5.6이고 형제가 쓴 가장 높은 번호는 1.5.5(`origin/dev`). `uv run python -m tools.check_constitution_version`은 커밋 전이라 "이 가지가 고친 헌법 파일이 없다"로 지나갔다(커밋 뒤 pre-commit이 다시 판정한다).
- 전체 pytest와 나머지 훅은 커밋이 부르는 pre-commit의 검사 러너가 돈다.

## 셀프 리뷰

`code-review` 스킬로 기준 `3cd84f5`(`origin/dev` 끝)에서 수정 20개 파일, 미추적 2개(티켓, 일지), 커밋 0개를 두 축으로 봤다. 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical과 Major는 없었다.

**고친 것.**
- ADR 0020 이력이 본문의 `"계약의 판 절"`을 인용했으나 본문에는 그 구절이 없었다(본문은 16행 "계약의 판을 적는다", 50행 "계약의 판만 적는 것"이다). 표준 축 Minor. 인용에서 그 구절을 뺐다.
- 헌법 `operations.md` 80행이 "위 표의 단계 이름 셋"이라 적었으나 표에는 `지난 릴리스의 GitHub 릴리스 확인` 하나뿐이고 `이미 공개된 릴리스`는 48행 단계 목록에, `릴리스 없음 알림`은 `release.yml`에만 있었다. 표준 축 Minor, 명세 축도 같은 곳을 짚었다. "이 문서와 `release.yml`의 단계 이름 셋"으로 고치고, 첫째 이름은 `판`뿐 아니라 `공개`도 `GitHub`으로 바뀐 것을 덧붙였다. ADR 0016 이력의 같은 설명도 맞췄다.
- `operations.md` 47행이 같은 단계 이름을 두 번 적었다(47행에서 같은 이름이 두 번 적힌 괄호). 표준 축 Nit. 괄호 속 되풀이를 뺐다.
- README가 티켓과 다르게 "첫 공개 릴리스"로 바뀌었고 "공개 릴리스"는 용어집에 없는 말이었다(두 축 Minor). "첫 릴리스"로 고치고 티켓의 README 항목을 실제와 맞췄다.
- 티켓과 일지가 `test_release.py`의 바뀐 시험 이름을 다섯이라 적었으나 여섯이었다(두 축). 숫자를 고쳤다.

**남긴 것과 이유.**
- Nit: "API 문서의 버전 칸", "MCP 서버 정보의 버전"이 릴리스 번호를 "버전"으로 부른다. 용어집은 릴리스의 피할 말에 "버전"을 적어 두었으나(버전 태그만 예외) 이 칸의 실제 이름이 `version`이고 ADR 0020 이력이 까닭을 적었다. 용어집에 칸 이름 `version`은 예외라는 한 줄을 더하는 것은 이 PR의 범위(이름 바꾸기)와 다른 용어집 개정이라 하지 않는다. 같은 판단이 홀로 쓰인 판 영역에서 다시 나오면 그 영역이 가른다.
- 명세 축이 참고로 적은 `tests/tools/test_deploy_guide.py` 94행의 "판을 바꾸기 전에"는 이미지 판을 가리키는 홀로 쓰인 판이라 다음 영역의 몫이다.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장).**
- `operations.md` 80행: "이 문서와 `release.yml`의 단계 이름 셋(`지난 릴리스의 GitHub 릴리스 확인`, `릴리스 없음 알림`, `이미 공개된 릴리스`)은 agent-os의 이름에서 `판`을 용어집의 `릴리스`로 바꾼 것이고, 첫째는 GitHub에 올리는 게시물임을 드러내려고 `공개`도 `GitHub`으로 바꿨다."
- ADR 0016 이력: "이 문서와 `release.yml`의 단계 이름 셋(`release.yml`에만 있는 `릴리스 없음 알림`까지)이 agent-os의 이름에서 `판`을 `릴리스`로 바꾼 것이라는 말(첫째 이름은 `공개`도 `GitHub`으로 바꿨다)이 되었다."
- ADR 0020 이력: 본문의 "릴리스 노트마다 그 제품 판에 든 계약의 판을 적는다"는 앞 이력대로 계약 버전을 적는 것으로 읽는다.
- README: "이 서버의 릴리스 번호는 semver다 … 첫 릴리스 0.1 전에는 `0.0.0`이다."

**다시 돌린 명령.** 고친 글은 문서뿐이라 코드는 다시 바뀌지 않았다. 아래 "커밋"의 pre-commit 결과가 갈음한다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 거부되어(앞 PR들과 같다) 보안 축은 내장 `/security-review`, 버그·성능 축은 `bug-perf-review` 에이전트로 대신했다.

**보안(`/security-review`).** 지적 없음. 스킬이 넘겨받은 diff 칸이 비어 있어(작업 트리가 아직 커밋 전이다) 보안과 닿는 파일(`release.yml`, `tools/release.py`, `tools/release_ci.py`, `tools/check_notes.py`, `src/rag_engine/main.py`, `src/rag_engine/adapters/release_number.py`, PR 서식)의 변경분을 `git diff -U0`로 직접 읽었다. 워크플로에서 바뀐 것은 단계의 표시 이름 셋과 주석 하나뿐이고 `run`, `if`, `env`, `permissions`, 비밀 값 참조, 표현식은 그대로다. 도구와 서버 코드에서 바뀐 것은 독스트링, 주석, 오류 문구, 도움말, 노트 제목 문자열이다.

**버그·성능(`bug-perf-review`).** 지적 0건(유효 0, 오탐 0). 기준 `3cd84f5`에서 수정 20개와 미추적 2개를 읽었고, 코드와 시험은 이름만 바뀌었다는 것을 다음으로 확인했다.
- `tools/release.py`의 새 문구(`계약 버전 줄이 비었다`, 코드 울타리 오류, 제목 `## 계약 버전`)가 `tests/tools/test_release.py`의 `match=`와 `in` 단언 6곳과 글자 그대로 같다. 노트 제목을 읽는 다른 코드(`check_notes.py`, `release.yml`, `main.py`)는 옛 제목에 기대지 않는다.
- 새 단계 이름 셋은 `release.yml`(93, 113, 405행)과 `operations.md`에만 있고, 그 이름을 `id`, `name`, `steps.<id>`, `gh run view` 조회로 찾는 코드는 없다. `merge.md`의 `gh run view` 식은 이름을 고정하지 않는다.
- 바뀐 시험 이름은 변이 표, 프로브 toml, pytest 설정에서 옛 이름으로 참조되지 않는다. 임시 파일 이름 `계약_버전.txt`는 윈도와 리눅스에서 문제없다.
- 헌법 버전 1.5.6은 형제의 가장 높은 번호 1.5.5보다 높고 `plan_table.py --check`도 통과한다.
- 밀 주장 확인: `operations.md` 80행이 말하는 이름 셋이 `operations.md`와 `release.yml`에 실제로 있고, agent-os의 `release.yml`(`C:\project\agent`)에서 원래 이름이 `지난 판의 공개 릴리스 확인`(81행), `판 없음 알림`(101행), `이미 공개된 판`(377행)이었다. ADR 0016·0020 이력의 행 번호와 따옴표 인용이 원문과 같다.
- 세지 못한 것: 일지의 "남은 25곳"과 "파일 16개"(위 "훑은 것"의 출력에서 옮긴 값이다)와 시험 통과 수.

**고친 것.** 없음(지적 0건). **남긴 것.** 없음. 반영한 셀프 리뷰 문장 넷은 이 리뷰가 확인한 밀 주장에 들어 있었다.

## 커밋

커밋 `c6e62a0`(23개 파일, +206/−57)은 pre-commit을 처음에 통과했다. 전체 pytest(1019초)를 포함한 검사 러너, ruff, 변이 표, 헌법 버전 검사, 커밋 메시지 검사가 모두 초록이었다. 헌법 버전 검사는 커밋 전에는 고친 헌법 파일이 없어 지나갔다가 이번에 비로소 1.5.6을 판정했다. 인용 대조 훅은 막지 않는 경고 8건을 냈다. 티켓과 일지가 옛 오류 문구나 선택 화면의 말을 큰따옴표로 풀어 옮긴 줄이었고, 원문과 글자가 같지 않았다. 따옴표를 떼고 요지로 다시 써서 다음 커밋에 실었다(티켓 9, 11, 40, 41행과 일지 19, 48, 53행).

푸시한 뒤 PR 87을 `dev`로 열었다. 본문은 앞 PR의 틀을 따라 헌법 문구 변경의 사용자 승인과 버전 1.5.5에서 1.5.6, 남긴 위험, 계약 영향을 적었다.

## 회고

`retro` 스킬의 4단계대로 후보 넷을 에이전트가 판정했다. 승인 1, 기각 3, 넘김 0이다.

- **승인: 병합된 이름 바꾸기 PR 뒤에 같은 때 열려 있던 PR이 옛 이름을 새 글에 다시 쓴다.** 사건: PR 78이 "계약의 판"을 바꿔 병합한 뒤 병합된 PR 80이 PR 서식 36행과 `tools/check_notes.py` 84행에 "계약의 판"을 새로 썼고, 어떤 검사도 막지 않아 이번 영역의 훑기가 찾을 때까지 남았다. 층: 검사(살아 있는 파일에서 버린 구절을 찾는 저장소 상태 시험). 되돌림: PR 하나로 되돌릴 수 있다. 더하는 검사라 다섯 번째에 반영하므로 새 항목 `renamed-term-reintroduced-by-parallel-pr`(1회차)로 대기열에 두었다. 같은 일을 다룬 열린 항목을 `queue_open_rows.py --search`로 찾았으나 없었다(맞은 넷은 용어집 이름 목록, 부하 ReadTimeout, 손으로 친 전체 pytest, 쟀다는 문장이고 모두 다른 일이다).
- **기각: 필터를 쓴 첫 훑기가 `## 계약의 판` 줄을 떨어뜨렸다.** 훑기 스크립트의 릴리스 낱말 필터와 슬라이스 오류가 겹쳤으나 양성 대조(`tools/release.py`의 "계약의 판" 열 자리)가 0으로 나와 같은 세션에서 바로 잡혔다. `rename-sweep-misses-forms`가 처방한 양성 대조가 제 몫을 했고 리뷰까지 새지 않았다. 5회차인 그 항목의 회차를 더하지 않는다.
- **기각: 이력에 본문에 없는 구절 `"계약의 판 절"`을 인용했다.** 표준 축 셀프 리뷰가 잡았다. 인용을 grep으로 본다는 기준은 `code-review`의 주장 검증 목록이 이미 가지고 있어 리뷰가 제 몫을 한 것이라 회차로 세지 않는다.
- **기각: `tidy-checkouts`의 `remove-branch`가 앱의 자동 분류기에 거부되었다.** 거부 뒤 우회하지 않고 보고했다. 이미 있는 앱 가드가 그 자리에서 막은 일이다.

## 다음

판 이름 바꾸기(지시문 `.scratch/glossary-names-input.md` 5-2 차례 5)의 남은 영역은 둘이다. 첫째는 홀로 쓰인 판이다. 번호를 가리키는 것(`format_version`, 라이브러리·이미지·액션·TEI·Docker 엔진의 판, 파일이나 도구의 사본과 개정을 뜻하는 판, alembic 개정의 판)과 밖에 내놓은 제품을 가리키는 것을 뜻에 따라 가른다. 둘째, 마지막은 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환, 스키마 판, 토크나이저 판)이고 사용자가 "버전으로 바꾼다"를 골랐다. 둘 다 한 PR로 하기에는 크므로 파일 묶음으로 나눠 영역마다 PR을 낸다. 시작 전에 `renamed-term-reintroduced-by-parallel-pr`가 닫혔는지 보고, 닫히지 않았으면 영역을 열기 직전에 열린 PR의 변경을 옛 구절로 훑는다.
