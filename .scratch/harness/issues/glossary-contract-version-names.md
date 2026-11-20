# glossary-contract-version-names: 계약에 붙이는 번호 "판"과 용어집의 판 항목을 "버전"으로 바꾼다

**What to build:** 사용자가 2026-11-18에 용어집의 이름을 agent-os에서 고른 이름과 맞추라는 지시문을 냈다(원문 `.scratch/glossary-names-input.md`). 그 일은 PR 여럿으로 차례로 하고, 이 티켓은 지시문 5-2의 차례 5 가운데 둘째 영역이다. 첫 영역(헌법 판, 비워 둔 판, 판 번호를 헌법 버전, 비워 둔 버전, 버전 번호로)은 PR 74로 병합되었다. 이 PR은 계약에 붙이는 번호를 가리키는 "판"을 "버전"으로 바꾼다. 계약은 헌법 원칙 VII이 드는 것이다: 검색 도구의 형식, 수집 API와 관리 API, 커넥터·변환·파서 인터페이스, 색인 형식. 용어집의 "판" 항목은 이 번호의 이름이므로 이름을 "버전"으로 바꾸고 피할 말 줄을 뒤집는다. 새 이름은 사용자가 agent-os에서 이미 골랐고 지시문 1절이 다시 묻지 않고 한다고 적었다. 앞말 없이 "버전"이라고만 쓰면 헌법 버전, 릴리스 번호와 헷갈리므로 계약을 가리킬 때는 "계약 버전"이라고 쓴다.

**고치는 곳.**
- `GLOSSARY.md`: 판 항목(이름을 "버전"으로, 풀이에서 칸을 더하고 지우는 규칙은 헌법 원칙 VII의 것이라 그대로 둔다), 그 항목의 피할 말 줄(전에는 "버전"을 피할 말로 적었으므로 뒤집어 옛 이름 "판"을 날짜와 함께 넣는다), 변경 확인값 항목의 피할 말 줄에 든 "계약의 판", 릴리스 항목의 "계약의 판"과 그 피할 말 줄의 "'판' 항목과 같은 까닭", 업그레이드 항목의 "계약의 판".
- 헌법(사용자가 2026-11-19에 문구를 승인했다. 아래 `## Comments`): `docs/constitution/principles.md`의 원칙 III 한 곳(판을 붙여 내는 계약), 원칙 VII의 제목과 본문, 거버넌스의 "판은 semver다"; `docs/constitution/operations.md`의 느낌표 기준 한 줄("계약의 판에서 앞자리를 올리는 변경"). 규칙은 그대로이고 낱말만 바뀐다. 헌법 `README.md`의 버전은 문구 수정(patch)으로 올린다. `tech.md`에는 계약 번호를 뜻하는 "판"이 없어(한 곳은 운영과 같은 이미지의 판이다) 고치지 않는다.
- `docs/PRD.md`의 성공 조건 한 줄("계약의 판 … 판 없이 깨지 않는다"). PRD 문구라 같은 승인을 받았다.
- 그 밖의 살아 있는 글: 루트 `README.md`(트리 설명의 `--version`과 `api_version.py` 두 곳), `.github/PULL_REQUEST_TEMPLATE.md`("올린 판", "계약 시험과 판"), `.claude/agents/spec-reviewer.md`의 계약 영향 항목, `.claude/skills/implement/SKILL.md`와 `.claude/skills/to-tickets/SKILL.md`의 한 곳씩, 아직 시작하지 않은 기능 계획(`.scratch/backup-upgrade/plan.md`, `.scratch/source-sync/plan.md`, `.scratch/doc-freshness/plan.md`)에서 계약의 번호를 뜻하는 곳.
- 코드의 독스트링, 주석, 설명과 시험 이름 가운데 위 계약의 번호를 뜻하는 곳: `src/rag_engine/server/`의 `api_version.py`·`ingest_models.py`·`admin_models.py`·`admin_knowledge_base_models.py`·`tool_models.py`(출력 스키마에 공개되는 `format_version` 칸의 설명 문자열 하나 포함), `src/rag_engine/domain/parsing.py`·`ports.py`, `src/rag_engine/adapters/parsers/registry.py`, `src/rag_engine/main.py`(`--version`의 도움말과 독스트링. 릴리스 노트 절 이름 "계약의 판"은 인용 그대로 둔다), `src/rag_engine/app/index_document.py`와 `tests/app/test_index_document.py`·`tests/adapters/test_parse_runner.py`의 "파서의 판"(코드의 `ParserVersion`이라 "파서 버전"으로 맞춘다), 시험 `tests/contract/`·`tests/domain/test_parsing.py`·`tests/adapters/test_docx_parser.py`·`tests/server/test_tool_models.py`·`tests/test_version_command.py`, `tests/server/test_release_number.py` 3행("검색 도구의 형식과 그 버전"). `release_number.py`와 그 시험의 "API 문서의 판 칸"은 릴리스 번호라 아래 "바꾸지 않는 것"이다.
- 옛 이름이 본문에 든 ADR(0003, 0007, 0008, 0010, 0012, 0013, 0015, 0017, 0018, 0019, 0020)은 본문을 두고 이력에 한 항목을 단다(0003은 이력 절을 새로 만든다). ADR 0005 본문의 "판"은 MCP SDK 라이브러리의 판이라 항목을 달지 않는다. 헌법 버전을 올린 까닭은 ADR 0016의 이력에 쌓는다.
- 대기열 항목 `glossary-plain-names-left`에 이 영역이 끝났음을 이어 쓴다.

**이번에 바꾸지 않는 것.** 다음 영역이 맡는다.
- PR 리뷰 봇의 지시문 `.github/workflows/claude-code-review.yml` 78행의 계약 번호 "판" 둘("계약이 바뀌었는데 판, 계약 시험", "계약의 판에서 앞자리를 올리는 변경"). 이 워크플로를 바꾼 PR은 일지·대기열·티켓·탐침 밖의 파일을 함께 실으면 같은 파일 96~125행의 가드가 실패시키므로 따로 PR로 낸다. 셀프 리뷰가 찾아 처음에는 고쳤다가 이 가드 때문에 되돌렸다.
- 릴리스 노트의 절 이름 "계약의 판"과 그에 묶인 글: `docs/constitution/operations.md`의 노트 절 차례 문장, release-image의 명세와 티켓, `.scratch/diag-bundle/plan.md`, `src/rag_engine/adapters/release_number.py`와 `tests/server/test_release_number.py`의 "API 문서의 판 칸". 형제 `02-tools-compute-release-number-notes-bundle`가 그 이름을 `tools/release.py`와 시험에 쓰는 중이라(2026-11-19에 읽었다) 둘이 어긋나지 않게 릴리스를 가리키는 판의 영역이 한 번에 맞춘다. 그 영역이 `--version`의 독스트링이 인용하는 절 이름도 맞춘다.
- 원칙 VII의 계약 목록에 들지 않은 파일 형식의 `format_version`(평가 세트 묶음, 추론 기록, 평가 보고서), 판정 지시문의 판, 라이브러리·이미지·TEI의 판. 번호를 가리키므로 "버전"이 맞지만 계약이 아니라서 홀로 쓰인 판의 영역이 가른다.
- 파일이나 도구의 사본·개정을 뜻하는 판(`sibling_overlap.py`의 "main 의 판", "커밋에 들 판", `tools.md`의 "옛 판", 스킬 주석의 "덧댄 판" 등), 서버·릴리스를 가리키는 판(루트 `README.md` 9행 "이 서버의 판", `.scratch/diag-bundle/plan.md`), alembic 개정을 뜻하는 판(`0001_initial_schema.py`의 "첫 판", `migrate.py`).
- 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환)과 그 요소인 "스키마 판", "토크나이저 판". 마지막 영역이다.
- 기록: 일지, ADR 본문, 끝난 기능(`core`, `search-eval`, `dev-branch`)의 명세·티켓·프로브, 닫힌 항목, 병합된 티켓, `.scratch/glossary-names-input.md`, agent-os에서 들여온 입력 글 `.scratch/kickoff-input.md`.
- 코드의 식별자, 설정 키, API의 칸 이름(`format_version`, `interface_version`, 경로의 `v1`), 파일 이름.

**대기열:** glossary-plain-names-left, rename-sweep-misses-forms, journal-cite-on-reworded-lines

**Status:** done

- [x] 용어집의 "판" 항목이 "버전"이 되었고 피할 말 줄이 "판"(옛 이름, 날짜)이다. 다른 항목의 피할 말에 든 "계약의 판", "'판' 항목과 같은 까닭"이 새 이름으로 맞는다
- [x] 헌법 문구 여섯 곳과 PRD 한 줄이 승인받은 대로만 바뀌고 `tech.md`와 다른 헌법 문장은 그대로다. 헌법 버전이 형제가 쓴 가장 높은 버전보다 높고 `Last Amended`가 오늘이며 `tools/check_constitution_version.py`와 `tools/sibling_overlap.py`가 통과한다. 올린 까닭이 ADR 0016의 이력에 있다
- [x] 위 "고치는 곳"의 코드 설명과 시험 이름이 새 이름을 쓰고, 바꾼 시험 이름을 이름으로 골라 돌리는 설정(변이 표, `pyproject.toml`, `.scratch`의 표)이 옛 이름을 가리키지 않는다. 훑은 명령과 결과는 일지에 있다
- [x] `tool_models.py`의 `format_version` 설명을 바꿔도 `tests/contract/`와 `tests/server/test_tool_models.py`가 초록이다
- [x] 옛 이름이 본문에 든 ADR의 이력에 이름을 바꿨다는 항목이 있고 본문은 그대로다. `tools/check_adr_pointers.py`가 초록이다
- [x] 계약의 번호를 뜻하는 "판"이 살아 있는 글에 남지 않았다. 남은 곳은 "바꾸지 않는 것"에 든 자리뿐이다. 찾은 명령과 결과는 일지에 있고, 줄바꿈으로 갈라진 꼴, 홀로 쓰인 "판", 줄여 부른 꼴로 훑었으며 출력이 빈 검색은 일치 없음으로 읽지 않고 양성 대조를 함께 쳤다(대기열 `rename-sweep-misses-forms`)
- [x] 조사를 확인했다. "버전"과 "판"은 받침이 같아 조사가 그대로인지 정규식으로 한 번 훑었다
- [x] 시험 이름이 길어져 줄 폭(한글 두 칸, 100칸)을 넘는 줄이 없고 `ruff format --check`가 초록이다
- [x] 사용자에게 보인 바뀌는 곳(헌법 여섯 곳과 PRD 한 줄)과 실제 바뀐 곳이 같다. 바뀐 파일 수는 일지와 마무리 보고에 적는다
- [x] 손으로 치는 검사 넷(린트, 포맷 검사, 타입체크, import 경계), 지침 검사 `tools/check_instructions.py`, 형제 겹침 `tools/sibling_overlap.py`, 전체 계획 `tools/plan_table.py --check`가 초록이고, 전체 pytest는 커밋의 검사 러너가 돌아 초록이다(결과는 일지)

## Comments

- 2026-11-19, 헌법과 PRD 문구를 고치는 근거. 이 세션의 첫 메시지(사용자의 글)가 "계약에 붙이는 번호를 뜻하는 판(… principles.md 원칙 VII과 거버넌스의 '판은 semver다', tech.md·operations.md …)을 '계약 버전'·'버전'으로 바꾼다"고 이 영역을 지시했고, 시작할 때 바뀔 곳을 여섯 곳으로 보이자 사용자가 선택 화면에서 "모두 승인"을 골랐다. 보인 곳: 헌법 여섯 곳(principles.md 12행, 원칙 VII 제목, 원칙 VII 본문, 거버넌스의 두 곳, operations.md 39행)과 docs/PRD.md 26행 한 줄. 규칙은 그대로이고 낱말만 바뀐다. 릴리스 노트의 절 이름 "계약의 판"은 형제 작업이 코드에 쓰는 중이라 이번에 두는 것도 그때 함께 보였다.
