# glossary-contract-version-names: 계약에 붙이는 번호 "판"과 용어집의 판 항목을 "버전"으로 바꾼다 · 2026-11-19

앞 세션(일지 `2026-11-19-0202-glossary-constitution-version-names.md`)이 PR 74를 병합하고 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-contract-version-names.md`, 브랜치는 `chore/glossary-contract-version-names`이고, 새 워크트리 `glossary-contract-version-names`에서 `origin/dev`(75cb8ea)로 브랜치를 따서 했다. 용어집의 이름을 agent-os의 결정에 맞추는 일(받은 지시문의 원문 `.scratch/glossary-names-input.md`)의 일곱째 PR이고, 받은 지시문 5-2의 차례 5 가운데 둘째 영역이다. 계기, 사용자에게 물은 것, 조사한 것, 한 것, 바꾸지 않고 남긴 것, 옛 이름의 잔존, 검증, 셀프 리뷰, 다음을 차례로 둔다.

## 계기

사용자가 아래 지시문을 첫 메시지로 넣어 이 세션을 열었다. 지시문의 핵심 줄이다.

```
받은 지시문 5-2의 차례 5 둘째 영역(계약에 붙이는 번호 "판"과 용어집의 판 항목, 헌법 문구를 "버전"으로 바꾸기)을 티켓 .scratch/harness/issues/glossary-contract-version-names.md로 쓰고 한다

다음 작업: 용어집의 "판"을 "버전"으로 바꾸는 일의 둘째 영역이다. 계약에 붙이는 번호를 뜻하는 "판"(GLOSSARY.md의 판 항목과 피할 말 줄, principles.md 원칙 VII과 거버넌스의 "판은 semver다", tech.md·operations.md, PR 서식의 "올린 판", 코드 설명)을 "계약 버전"·"버전"으로 바꾼다
이어받을 상태: 헌법 문구는 시작할 때 바꿀 내용을 사용자에게 보이고 승인받는다. 릴리스를 가리키는 "판"은 PR 73 병합 뒤 영역이라 건드리지 않는다. 색인 판 계열은 마지막 영역이다
이번 요청 범위: PR과 병합까지
```

이 일은 retro가 승인한 대기열 항목이 아니라 사용자의 직접 지시다. 티켓의 대기열 줄에는 `glossary-plain-names-left`(이름을 바꾸는 일 전체), `rename-sweep-misses-forms`, `journal-cite-on-reworded-lines`를 적었다.

## 사용자에게 물은 것

헌법과 PRD의 문구는 사용자 승인으로만 고친다. 시작할 때 바꿀 곳 여덟 가지를 선택 화면에 보였다. 헌법 여섯 곳(`principles.md` 12행, 원칙 VII의 제목, 원칙 VII의 본문, 거버넌스의 "헌법 버전은 semver다", `operations.md` 39행)과 `docs/PRD.md` 26행 한 줄, 헌법 버전을 patch로 올리는 것, 릴리스 노트의 절 이름 "계약의 판"은 이번에 두는 것이었다. 사용자는 "모두 승인"을 골랐다. 근거는 티켓의 `## Comments`에 적었다. 규칙은 그대로이고 낱말만 바뀐다.

## 조사한 것

낱말 "판"이 여러 뜻으로 쓰이고 있어 모든 "판"을 바꿀 수는 없었다. 기준은 헌법 원칙 VII이 드는 계약 목록(검색 도구의 형식, 수집 API와 관리 API, 커넥터·변환·파서 인터페이스, 색인 형식)에 붙는 번호인가이다.

- 바꾼다: 위 계약의 번호, 그리고 그것을 부르는 용어집·헌법·PRD·PR 서식·스킬·리뷰 봇 지시문의 말.
- 두 영역 뒤로 미룬다: 릴리스 번호를 가리키는 판(API 문서의 판 칸, MCP `serverInfo.version`, 릴리스 노트의 절 이름 "계약의 판", `--version` 출력과 묶인 글), 색인 판 계열, 파일이나 도구의 사본·개정을 뜻하는 판.
- 계약이 아니라서 두는 것: 평가 묶음·추론 기록·평가 보고서의 `format_version`, 판정 지시문의 판, 라이브러리·이미지·TEI의 판, alembic 개정.

형제 워크트리 `02-tools-compute-release-number-notes-bundle`가 릴리스 노트의 절 이름 "계약의 판"을 `tools/release.py`와 시험에 쓰는 중이라(헌법 버전 1.5.2를 쓰고 있다), 그 이름과 묶인 글은 릴리스 영역이 한 번에 맞추도록 남겼다. `main.py`의 `version_lines` 독스트링은 그 절 이름을 인용 그대로 두고 나머지 낱말만 바꿨다.

"판"과 "버전"은 받침이 같아(ㄴ) 조사가 달라지지 않는다.

## 한 것

- **용어집.** "판" 항목을 "버전" 항목으로 바꿨다. 풀이에 "계약에 붙은 것은 '계약 버전', 헌법에 붙은 것은 '헌법 버전'이라고 앞말을 붙여 부른다"를 넣었다. 피할 말은 `판(옛 이름. 2026-11-19에 바꿨다)`이다. 릴리스 항목의 "계약 버전, 색인 판과는 따로 센다", 그 피할 말 `버전(계약 버전·헌법 버전과 헷갈린다. …)`, 업그레이드 항목의 "계약 버전을 올리는 일은 이 말로 부르지 않는다"와 `판 올림(옛 이름. …)`, 변경 확인값의 `버전(계약 버전과 헷갈린다)`을 맞췄다.
- **헌법과 PRD(승인된 대로).** `principles.md`는 12행, 원칙 VII의 제목과 본문, 거버넌스의 두 곳. `operations.md`는 39행의 느낌표 기준 한 줄. `docs/PRD.md`는 26행. 헌법 `README.md`의 버전은 1.5.3(`Last Amended` 2026-11-19)이다. 형제 02가 1.5.2를 매기고 있어 그 위로 골랐고, 1.5.2는 비워 둔 버전 문장으로 남겼다.
- **그 밖의 살아 있는 글.** 루트 `README.md` 두 곳, `.github/PULL_REQUEST_TEMPLATE.md` 두 곳, `.claude/agents/spec-reviewer.md` 19행, `.claude/skills/implement/SKILL.md` 13행, `.claude/skills/to-tickets/SKILL.md` 21행, 아직 시작하지 않은 기능 계획 셋(`backup-upgrade`, `source-sync`, `doc-freshness`).
- **코드의 설명(식별자와 동작은 그대로).** `src/rag_engine/server/`의 `api_version.py`, `ingest_models.py`, `admin_models.py`, `admin_knowledge_base_models.py`, `tool_models.py`(출력 스키마로 공개되는 `format_version` 칸의 설명 문자열 하나 포함), `domain/parsing.py`, `domain/ports.py`, `adapters/parsers/registry.py`, `main.py`(`--version` 도움말과 독스트링), `app/index_document.py`(두 곳)의 "파서의 판". 마지막 것은 코드의 `ParserVersion`(파서 이름, 인터페이스 버전, 라이브러리 버전)을 말하는데 `domain/parsing.py`는 이미 "버전"으로 바꾸어 한 개념의 말이 갈렸으므로 "파서 버전"으로 맞췄다. 시험 이름과 독스트링은 `tests/domain/test_parsing.py`, `tests/adapters/test_docx_parser.py`, `tests/contract/test_read_tools.py`, `tests/contract/test_search_tool.py`, `tests/server/test_tool_models.py`, `tests/test_version_command.py`, `tests/server/test_release_number.py` 3행에 더해 `tests/app/test_index_document.py`(독스트링 한 곳과 시험 이름 둘)와 `tests/adapters/test_parse_runner.py`(시험 이름 셋)다. 출력 스키마의 설명 문자열을 계약 시험이 고정하지 않는지 먼저 읽어 확인했고(`tests/contract/`와 `test_tool_models.py`가 그 글자를 단언하지 않는다), 바꾼 시험 이름을 이름으로 가리키는 변이 표, `pyproject.toml`, `.scratch`의 설정이 없는지 이름으로 훑었다. 정의 줄만 나왔다.
- **ADR 이력.** 본문은 두고 이력 항목만 더했다. ADR 0016에는 헌법 버전을 1.5.3으로 올린 까닭을(1.5.2가 형제 몫으로 비는 번호라는 것 포함), ADR 0003(이력 절이 없어 `## 이력`을 만들었다), 0007, 0008, 0010, 0012, 0013, 0015, 0017, 0018, 0019, 0020에는 "용어집이 계약에 붙이는 번호의 이름을 판에서 버전으로 바꿨다"를 달았다. 각 항목은 본문 어느 말을 어떻게 읽는지 적고, 릴리스를 가리키는 판이나 색인 판 계열 같은 계약이 아닌 쓰임은 그대로라고 밝혔다. ADR 0005는 처음에 항목을 달았다가 되돌렸다(아래 "셀프 리뷰"). 0017 본문의 `(바뀜: 이력 2026-11-17 "…판을 1.1.0으로 올린다")` 포인터는 이력 제목을 글자 그대로 인용하므로 제목을 고치지 않았다.
- **대기열.** `.scratch/retro-queue/glossary-plain-names-left.md`에 차례 5의 둘째 영역을 마쳤고 헌법 버전이 1.5.3이 된다는 것, 남은 판이 릴리스 번호를 가리키는 판, 평가 묶음의 `format_version`, 사본을 뜻하는 판, 색인 판 계열이라는 것을 단락으로 이었다.

## 바꾸지 않고 남긴 것

티켓의 "바꾸지 않는 것"과 같다.

- PR 리뷰 봇의 지시문 `.github/workflows/claude-code-review.yml` 78행의 계약 번호 "판" 둘(아래 "셀프 리뷰"의 까닭으로 따로 PR을 낸다).
- 릴리스 번호를 가리키는 판: `docs/constitution/operations.md` 31행의 "계약의 판" 절 이름, `src/rag_engine/adapters/release_number.py`와 `tests/server/test_release_number.py` 1행의 "API 문서의 판 칸", 루트 `README.md` 9행의 "이 서버의 판", `.scratch/release-image/`의 명세와 티켓, `.scratch/diag-bundle/plan.md`.
- 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환, 스키마 판, 토크나이저 판)과 용어집 75~87행의 그 피할 말 줄.
- 계약 목록에 들지 않은 `format_version`(평가 세트 묶음, 추론 기록, 평가 보고서)과 판정 지시문의 판, 라이브러리·이미지·TEI의 판, alembic 개정.
- 파일이나 도구의 사본·개정을 뜻하는 판(`sibling_overlap.py`, `mutate.py`, 스킬 주석의 "덧댄 판" 등).
- 기록: 일지, 끝난 기능(`core`, `search-eval`, `dev-branch`)의 명세·티켓·프로브, 닫힌 항목, `.scratch/glossary-names-input.md`, `.scratch/kickoff-input.md`. ADR 0006 이력의 옛 이름 "헌법 판"(PR 74 리뷰의 Nit)은 지난 이력 항목 안의 글이라 기록으로 두었다. `.claude/rules/adr.md`가 지난 이력은 고치지 않는다고 정한다.

## 옛 이름의 잔존

잔존 훑기를 세 번 했다. 처음의 구절 꼴(`계약의 판`, `판을 올`, `판 없이`, `형식의 판`)만으로는 홀로 쓰인 판을 놓칠 수 있어(대기열 `rename-sweep-misses-forms`), 스크래치패드의 스크립트로 추적 파일 전체에서 앞이 한글이 아닌 "판"을 모두 찾아 앞뒤 40자와 함께 냈다. 파일 읽기는 UTF-8로 했다.

1. 첫 훑기는 출력 줄을 앞 200자에서 잘라 뒤쪽 일치가 가려졌다. 그 잘림 때문에 `.github/workflows/claude-code-review.yml` 78행의 "계약이 바뀌었는데 판, 계약 시험"과 "계약의 판에서 앞자리를 올리는 변경"을 처음에는 놓쳤다. 일치 지점의 앞뒤 40자만 내도록 스크립트를 고쳐 다시 쳤다.
2. 다시 쳐서 `.claude/skills/implement/SKILL.md` 13행의 "계약의 판에서 앞자리를 올리는 변경"과 `.claude/skills/to-tickets/SKILL.md` 21행의 "색인 형식의 판"을 더 찾았고 고쳤다.
3. 줄 첫머리에서 갈린 꼴(줄이 "판"으로 시작하는 곳)은 Grep으로 따로 쳤다. 나온 것은 모두 색인 판, 사본·개정, 라이브러리 판의 쓰임이었다.

양성 대조로 알려진 일치(루트 `README.md` 9행 "이 서버의 판", `compose.test.yml`의 "운영과 같은 판")가 출력에 나오는지 보았다. 남은 곳은 모두 위 "바꾸지 않고 남긴 것"에 든 자리다. 조사 어긋남은 `버전(는|를|가|와|로)`를 `*.md`, `*.py`, `*.yml`에 걸어 훑었다. 일치는 지시문이 예시로 인용한 `"버전는"`과 앞 일지의 서술뿐이고, 같은 정규식이 그 인용을 잡았으니 정규식 자체는 작동한다.

## 검증

손으로 친 것은 다음과 같다. 파이프 없이 하나씩 쳤다.

- `uv run ruff check .`: 통과. `uv run ruff format --check .`: 766개 파일 이미 맞음. `uv run pyright`: 오류 0개. `uv run lint-imports`: 2개 지킴, 0개 깨짐. 줄 길이를 넘긴 두 곳(`main.py`, `tool_models.py`)은 `tools/rewrap_comments.py`로 감았다.
- `uv run python tools/check_instructions.py`, `uv run python tools/check_adr_pointers.py`, `uv run python tools/plan_table.py --check`: 출력 없이 통과.
- `uv run python -m tools.check_constitution_version`: 커밋 전이라 "이 가지가 고친 헌법 파일이 없다"로 나온다(커밋 뒤의 훅이 판정한다).
- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 이 브랜치의 새 번호는 헌법 1.5.3. 형제 최고는 1.5.2(워크트리 02). 형제 02도 `docs/constitution/README.md`와 `operations.md`를 고쳐 나중에 병합하는 쪽에서 글자 충돌이 날 수 있다는 알림이 나왔다.
- 시험 데이터베이스(`docker compose -f compose.test.yml up -d --wait`, `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`)를 띄우고 `uv run pytest tests/domain/test_parsing.py tests/server/test_tool_models.py tests/test_version_command.py tests/server/test_release_number.py tests/adapters/test_docx_parser.py tests/contract tests/tools/test_check_adr_pointers.py -q`: 138개 통과(341초). 환경 변수 없이 처음 쳤을 때의 오류는 데이터베이스가 없다는 설정 문제였고 코드와 무관했다.
- 전체 `uv run pytest`는 커밋이 부르는 pre-commit의 검사 러너가 돈다.

셀프 리뷰 반영 뒤에 `ruff check`, `ruff format --check`(767개), `pyright`(오류 0개), `tools/check_adr_pointers.py`, `tools/check_instructions.py`를 다시 쳤고 모두 통과했다. `tools/sibling_overlap.py`는 번호 겹침 없음, 이 브랜치의 새 번호 1.5.3이다(형제 02는 PR 77로 열렸고 헌법 1.5.2를 쓴다). `uv run pytest tests/app/test_index_document.py tests/adapters/test_parse_runner.py -q`: 51개 통과(41초).

pyright가 시험 파일의 안 쓰는 인자 힌트를 내지만 이 변경 이전부터 있던 것이다.

## 셀프 리뷰

`code-review` 스킬로 기준 `75cb8ea`(`origin/dev` 끝)에서 수정 41개 파일과 미추적 2개(티켓, 이 일지), 커밋 0개를 두 축으로 봤다. 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical은 없었다. 사실이 틀린 글이 Major 하나(ADR 0005 이력), 이름 바꾸기가 놓친 계약 번호가 Major 하나(ADR 0019·0020 본문과 "파서의 판"), 범위 위반이 하나(리뷰 봇 워크플로)였다.

**고친 것.**
- ADR 0005 이력이 틀렸다(명세 축). 본문 19행의 "2.x는 출시 몇 달 된 판이라 minor 판에서 …, 판을 올릴 때"는 앞뒤가 모두 MCP SDK 라이브러리의 판이라 계약 번호가 아니다. 이력 항목과 새로 만든 `## 이력` 절을 되돌렸다(`git checkout`으로 이 세션의 편집만 되돌렸다).
- `.github/workflows/claude-code-review.yml` 78행의 계약 번호 "판" 둘을 처음에 고쳤으나 되돌렸다(명세 축). 이 파일을 바꾼 PR은 같은 파일 96~125행의 가드가 일지·대기열·티켓·하네스 탐침 밖의 파일이 함께 실리면 `exit 1`로 실패시킨다. 5~6행 주석대로 봇도 이 PR을 건너뛴다. 따로 PR로 내기로 하고 티켓의 "바꾸지 않는 것"에 까닭과 함께 적었다.
- ADR 0019 본문 10행("판을 붙여 밖에 여는 인터페이스가 아니며")과 ADR 0020 본문 15, 16, 23, 50행의 계약 번호 "판"에 이력 항목을 달았다(표준 축). 0020 23행의 "용어집의 '판'은 계약과 헌법의 번호이고"는 용어집에서 판 항목이 없어졌으므로 이 PR이 거짓으로 만든 문장이다. 이어 ADR 0010 10행("ADR 0003의 판을 올리는 일이라서다")과 ADR 0013 10행("파서 판이 올랐을 때")도 명세 축이 찾아 항목을 달았다.
- ADR 0016 이력 항목의 빈 주장("이 ADR의 본문과 앞 이력에 든 계약 번호의 '판'은 …")을 뺐다. 0016 본문의 "판"은 헌법 판뿐이다. 헌법 변경 나열에 원칙 III의 한 곳도 더했다.
- ADR 0015 항목에 빠진 22행 "두 판을 함께 유지", 23행 "서버 수준 판 하나"와 "도구마다 판을 따로 올릴 수 없다"를 더했다. ADR 0017 항목의 "판." 항목이 13행과 이력 56행 두 곳임을 밝혔다. ADR 0008 항목에는 본문이 "색인 형식의 판"과 "색인 판 레코드"를 한 문장에 나란히 적으므로 마지막 영역이 함께 맞춘다고 더했다.
- "파서의 판"을 "파서 버전"으로 맞췄다(양 축). `domain/parsing.py`의 `ParserVersion`은 이미 "버전"으로 바꿨는데 `app/index_document.py` 7·277행, `tests/app/test_index_document.py` 39행과 시험 이름 둘, `tests/adapters/test_parse_runner.py`의 시험 이름 셋이 "판"이어서 한 값의 말이 갈렸다. 바뀐 시험 이름을 이름으로 가리키는 곳은 없다.
- `.scratch/backup-upgrade/plan.md` 5·9행의 "옛 버전의 색인을 새 버전이 읽는지"는 둘째 "버전"이 서버를 가리켜 용어집의 릴리스와 겹친다(표준 축). "옛 색인 형식 버전의 색인을 새 릴리스가"로 바꿨다.
- 티켓의 Comments가 "여섯 곳"을 세는 방식이 사용자에게 보인 라벨과 달랐다. 헌법 여섯 곳과 PRD 한 줄로 고쳤다. 티켓의 ADR 목록과 코드 목록을 실제 변경에 맞췄다.

**남긴 것과 이유.**
- `.scratch/diag-bundle/plan.md` 7행과 `.scratch/release-image/spec.md` 149행의 "계약마다 판", `<계약의 이름> <판>`: `--version`의 출력과 릴리스 노트의 "계약의 판" 절에 묶인 글이라 티켓이 릴리스 영역으로 넘긴 파일이다. 이 PR이 `main.py`의 독스트링만 "계약 버전"으로 바꿔 한동안 말이 갈린다. 릴리스 영역(PR 77 병합 뒤)이 한 번에 맞춘다.
- `.scratch/retro-queue/stale-checkout-at-session-start.md` 7행의 "형식의 판": 사건을 적은 기록이다.
- 한 낱말을 영역으로 나눠 바꾸는 데서 오는 임시 불일치(`operations.md` 31행의 "계약의 판"과 39행의 "계약 버전")는 냄새로 보이지만 지시문이 정한 순서의 결과다.
- 표준 축이 짚은 용어집 "75~87행" 인용은 일지의 줄 번호 서술이 실제와 조금 다르다는 지적이다. 일지가 기록이라 고치지 않고 아래 PR 직전 리뷰에서 다시 본다.

**다시 돌린 명령.** 위 "검증"의 마지막 문단에 있다. 전체 pytest는 커밋이 부르는 pre-commit의 검사 러너가 돈다.

**PR 직전 리뷰에 밀 주장(이번 반영으로 새로 쓴 사실 문장의 원문).**
1. 티켓: "이 워크플로를 바꾼 PR은 일지·대기열·티켓·탐침 밖의 파일을 함께 실으면 같은 파일 96~125행의 가드가 실패시키므로 따로 PR로 낸다."
2. ADR 0010 항목: "본문의 '플러그인 자리를 셋으로 정한 ADR 0003의 판을 올리는 일이라서다'에서 판은 ADR 0003이 정한 인터페이스의 버전이라 '버전'으로 읽는다."
3. ADR 0013 항목: "'파서 판'은 코드의 `ParserVersion`(파서 이름, 파서 인터페이스의 버전, 라이브러리의 버전)이라 '파서 버전'으로 읽는다."
4. ADR 0019, 0020 항목: 본문 줄 번호(0019 10행, 0020 15·16·23·50행)와 인용 구절이 본문과 글자 그대로인지.
5. "`ParserVersion`"이 파서 이름과 두 버전을 가진다는 서술이 `src/rag_engine/domain/parsing.py`의 정의와 맞는지.

## 커밋

`8b567a2`(`chore: 계약 번호의 판을 버전으로 바꾼다 (harness glossary-contract-version-names)`), 47개 파일에 276줄 추가와 75줄 삭제다. 커밋이 부른 pre-commit이 린트, 포맷 검사, 타입체크, import 경계, 전체 pytest를 돌려 모두 통과했다. 위 "검증"에서 전체 pytest를 pre-commit에 맡긴다고 적은 부분의 결과가 이것이다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 거절되어 돌지 못했다. 대신 두 가지를 돌렸다.

- `bug-perf-review` 서브에이전트(버그·성능): 지적 0건(Critical, Major, Minor 모두 0). 동작이 바뀐 줄이 없다는 것과, `uv run python -m rag_engine.main --version`이 아무것도 찍지 않는 것은 이 변경 이전부터 `__main__` 가드가 없어서라는 것을 짚었다. 확인은 `uv run rag-engine --version`으로 한다.
- 내장 `/security-review`(보안): 지적 없음.

둘 다 문서, 독스트링, 시험 이름, 설명 문자열만 바뀐 변경이라는 판정과 일치한다.

## PR 봇 회차

PR 78(`https://github.com/njh6803/rag-engine/pull/78`).

- 첫 회차, claude-review: 지적 없음. 코드의 바뀐 줄이 독스트링, 주석, 시험 이름, `--version` 도움말, `_VERSION_DESCRIPTION`뿐이고 `FORMAT_VERSION`(1.1.0)과 경로 접두 `v1`이 그대로라고 확인했다. 제목 접두 `chore:`도 맞다고 했다.
- CodeRabbit: 무료 리뷰 한도에 걸려 리뷰하지 못했다(`Review rate limited`, 다음 리뷰는 약 30분 뒤). 리뷰 요청 코멘트에도 같은 답이 왔다. 마지막 푸시 커밋에 리뷰를 받은 적이 없으므로 이 PR의 CodeRabbit 회차는 세지 않는다.
- 검사: `python`, `image`, `eval-fast`, `eval-full`, `ticket`, 필수 검사 `verify`가 모두 통과했다.

## 회고

후보 다섯, 판정은 승인 둘, 기각 셋, 넘김 없음이다.

1. **옛 이름 훑기가 형태를 놓친다(`rename-sweep-misses-forms`) — 승인, 5회차.** 사건: 옛 이름 "판"을 구절 꼴로 훑은 첫 스크립트가 출력 줄을 앞 200자에서 잘라, 뒤쪽 일치(리뷰 봇 지시문 yml, `implement`와 `to-tickets` 스킬)를 놓쳤고, 셀프 리뷰 두 축이 "파서의 판"과 ADR 0010·0013·0019·0020 본문의 계약 번호 "판"을 더 짚었다. 층: 새 `tools/` 훑기 도구(검사로 승인). 되돌림: PR 하나로 가능하다. 더하는 것이라 다섯 번째에 반영한다. 이 세션이 그 다섯 번째지만, 도구를 새로 만드는 일이라 이미 봇 회차 중인 이 PR에 싣지 않고 대기열의 chore 배치 조건(회차 5 이상)으로 둔다. 항목에 5회차를 더하고, 도구가 일치 지점의 앞뒤 글자를 내고 UTF-8로 읽고 양성 대조를 함께 치게 하라는 설명을 더했다. 남은 이름 바꾸기 영역(릴리스를 가리키는 판, 홀로 쓰인 판, 색인 판 계열)이 이 도구를 바로 쓴다.
2. **`python -I`와 cp949(`python-i-utf8`) — 승인, 7회차.** 사건: 옛 이름을 훑는 스크립트의 한글 출력에서 cp949 `UnicodeEncodeError`가 났고 `-I -X utf8`로 풀었다. 열린 항목이 이미 처방한 사건이라 승인 줄에 7회차를 더했다(6회차에서 이미 chore 배치 조건이다).
3. **리뷰 봇 지시문 yml을 다른 파일과 함께 고치면 가드가 실패한다 — 기각.** 이 PR의 첫 편집이 그 가드(`claude-code-review.yml` 96~125행)에 걸릴 뻔했고 셀프 리뷰 명세 축이 짚어 되돌렸다. 가드는 CI가 `exit 1`로 막고 PR 서식의 `.github/` 항목도 같은 규칙을 적고 있다. 이미 있는 검사가 그 자리에서 막는 것이라 기각이다.
4. **ADR 0005 이력에 라이브러리의 "판"을 계약 번호로 적은 사실 오류 — 기각.** 셀프 리뷰 명세 축이 잡아 그 턴에 되돌렸다. 리뷰가 제 몫을 한 것이라 회차로 세지 않는다.
5. **테스트 PostgreSQL 없이 전체 시험을 쳐서 설정 오류가 난 것 — 기각.** `CLAUDE.md`의 검증 명령 절이 환경 변수와 띄우는 방법을 이미 적고 있다.

만료할 항목은 없다(`queue_open_rows.py`가 "(없음)"으로 답했다).

## 다음

1. 이 PR의 병합 뒤 병합 보고에 `주 체크아웃 미갱신: 루트는 <브랜치>` 한 줄이 따른다. 병합 전에 쓰는 일지라 그 값은 여기 적지 않는다.
2. 따로 PR로 낼 일: `.github/workflows/claude-code-review.yml` 78행의 계약 번호 "판" 둘("계약이 바뀌었는데 판, 계약 시험", "계약의 판에서 앞자리를 올리는 변경")을 "계약 버전"으로 바꾼다. 그 파일은 같은 파일의 가드(96~125행) 때문에 일지·대기열·티켓·탐침 밖의 파일과 함께 실을 수 없다. 그 PR은 claude-review가 건너뛰므로 CodeRabbit 코멘트와 셀프 리뷰를 손으로 본다. 이 PR이 병합된 뒤에 낸다.
3. 이름 바꾸기의 남은 영역: 릴리스를 가리키는 판(PR 77이 dev에 병합되어 이제 시작할 수 있다. 릴리스 노트 절 이름 "계약의 판"은 `tools/release.py`와 `operations.md`에 쓰인다), 홀로 쓰인 판과 `format_version`, 색인 판 계열(마지막). 영역마다 시작할 때 위 대기열 `rename-sweep-misses-forms`의 훑기 모양(일치 지점의 앞뒤 글자, UTF-8, 양성 대조)을 지킨다.
4. 대기열에서 chore 배치 조건(회차 5 이상)이 찬 항목은 `rename-sweep-misses-forms`(5회차)를 더해 열다섯 개다. 기능의 마지막 티켓 뒤에 결정표가 고른다.
5. 형제 PR 77이 이 PR보다 먼저 dev에 병합되어(`9d09885`, 헌법 1.5.2) `docs/constitution/README.md`의 버전 줄이 충돌했다. `origin/dev`를 이 브랜치에 합치며 버전은 1.5.3을 그대로 두고, 형제가 1.5.2를 가져갔으므로 "1.5.2는 함께 돌던 형제 브랜치가 먼저 매겨 비워 두었다" 문장을 지웠다(README가 정한 규칙). `operations.md`는 글자 충돌 없이 합쳐졌고, 합쳐 들어온 `operations.md`와 `tools/release.py`를 "판"으로 훑어, 계약 번호를 뜻하는 "판"이 새로 들어오지 않았음을 확인했다(일치는 "판정", 릴리스 노트 절 이름 "계약의 판", 릴리스 쪽 쓰임뿐이고 모두 릴리스 영역의 몫이다). ADR 0016 이력의 "1.5.2는 형제 몫으로 비는 번호"는 그 시점의 기록이라 고치지 않았다.
