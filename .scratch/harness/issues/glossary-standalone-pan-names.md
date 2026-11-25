# glossary-standalone-pan-names: 하네스·테스트·배포 파일에 홀로 쓰인 판을 버전으로 바꾼다

**What to build:** 사용자가 2026-11-18에 용어집의 이름을 agent-os에서 고른 이름과 맞추라는 지시문을 냈고(원문 `.scratch/glossary-names-input.md` 5-2 차례 5), 그 일은 영역별 PR로 한다. 앞 영역은 헌법 버전(PR 74), 계약에 붙이는 번호(PR 78), 리뷰 봇 지시문(PR 79), 릴리스 번호(PR 87)로 병합되었다. 이 티켓은 홀로 쓰인 판 영역이다. 번호를 붙인 소프트웨어, 도구, 이미지의 버전을 뜻하거나 파일의 시점 사본을 뜻하는데 앞 영역들이 홀로 쓰인 판의 영역이 가른다며 미뤄 둔 글이다. 용어집의 버전 항목은 아직 계약과 헌법의 번호만 풀이하므로 항목을 넓히는 일은 용어집을 바꾸는 마지막 영역에 맡긴다.

**고치는 곳.** 앞뒤가 한글이 아니고 뒤에 정·단·별·매가 오지 않는 판을 버전으로 바꾼다. 파일 70여 개, 약 270곳이다. 먼저 하네스 묶음(`tools/`, `tests/tools/`, `.claude/`, `.github/`, `docs/agents/`, 루트의 `pyproject.toml`·`compose.test.yml`·`.pre-commit-config.yaml`, `deploy/`, `tests/standalone/`)에서 홀로 쓰인 판을 줄 통째로 뽑아 뜻을 가렸다. 대부분 버전(도구·이미지·액션의 번호, 첫 판처럼 고쳐 가며 생긴 구현)을 뜻했다. 약 60곳은 번호가 아니라 파일이나 색인의 시점 사본(`main 의 판`, `부모 판`)을 뜻했고, 자연스러운 말인 버전으로 바꾸되 한 글 안에서 번호와 섞여 헷갈리는 구절 `커밋에 들 판(색인)`(`tools/check_constitution_version.py`, `tools/mutate.py`, 그 시험들, `.pre-commit-config.yaml`)은 내용으로 적었다. 다른 뜻이 섞인 곳은 아래 바꾸지 않는 것이다.
- 시험 함수 이름 아홉 개에 든 판도 문장의 일부라 함께 바꾸었다(`tests/tools/test_mutate.py`, `test_hook_grep_omitted.py`, `test_run_checks_database.py`, `test_sibling_overlap.py`). 옛 이름 조각은 저장소에서 grep해 참조가 없다.
- 스킬 머리 주석의 `agent-os가 덧댄 판`은 `덧댄 버전`이 된다.
- 테스트 독스트링과 도구 주석의 `첫 판`, `옛 판`, `~던 판`은 `첫 버전`, `옛 버전`, `~던 버전`이 된다.
- 설정과 배포 파일의 `TEI CPU 판`, `운영과 같은 판`, `판은 uv.lock이 고정한다`는 버전이 된다.
- 한글 두 칸 폭 때문에 길어진 주석과 독스트링은 `tools/rewrap_comments.py`로 다시 감았다.
- 헌법 `docs/constitution/tech.md` 두 곳(11행과 23행)과 `docs/PRD.md` 19행은 사용자 승인을 받아 바꾼다(아래 `## Comments`). 규칙은 그대로이고 낱말만 바뀌는 문구 수정이라 헌법 버전은 1.5.6에서 1.5.7(patch)로 오른다. 올리는 까닭은 ADR 0016의 이력에 쌓고 `docs/constitution/README.md`의 `Version`을 맞춘다.
- 바꾼 줄에 든 `일지 <날짜>-<번호>` 인용 가운데 agent-os의 일지를 가리켜 이 저장소에 없는 것은 `tools/sibling_overlap.py`가 어디에도 없는 인용으로 알리므로, 인용의 번호를 코드 스팬으로 감쌌다(그 도구가 일부러 없는 이름이면 코드 스팬에 넣으라고 안내한다).

**이번에 바꾸지 않는 것.**
- 기록. 일지, ADR 본문, 끝난 기능의 명세·티켓·프로브, 병합된 티켓, 닫힌 항목, `.scratch/glossary-names-input.md`, `.scratch/kickoff-input.md`.
- 파다(掘)의 활용인 판(`워크트리를 판다`, `손으로 판 워크트리`, `폴더에 판 것`). 글자 모양만으로는 가려지지 않아 줄마다 눈으로 가렸다.
- 남의 결정 이름 인용. `release.yml` 442행의 agent-os ADR 0056 결정 이름 `판 내기의 차례와 실패`.
- 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 스키마 판). 사용자가 앞서 버전으로 바꾼다를 골랐으나 마지막 영역(src와 평가 묶음, 용어집, 마이그레이션 문서)과 함께 낸다. 이 PR의 두 줄(`tests/tools/test_check_notes.py` 875행, `.claude/skills/code-review/SKILL.md` 108행)도 거기에 맡긴다.
- 검색 평가 도구와 시험(`tools/search_eval.py`, `tests/tools/test_search_eval*`, `compose.eval.yml`), `GLOSSARY.md`, `README.md`, `docs/constitution/operations.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/claude-code-review.yml`. `claude-code-review.yml`을 뺀 나머지는 마지막 영역의 몫이다. `claude-code-review.yml`은 이 워크플로 파일을 바꾸는 PR이 일지·티켓·프로브 밖의 파일을 함께 싣지 못하는 검사가 있어 따로 작은 PR로 낸다.
- 판정, 판단, 판별, 판매 같은 낱말의 일부.
- 코드의 식별자, 설정 키, API의 칸 이름, 파일 이름.

**대기열:** glossary-plain-names-left, renamed-term-reintroduced-by-parallel-pr, commit-msg-after-slow-checks

**Status:** done

- [x] 위 고치는 곳의 파일에서 홀로 쓰인 판이 뜻을 가려 버전으로 바뀌었고, 파다의 활용과 남의 결정 이름은 남았다
- [x] 헌법 버전이 1.5.7이고 `docs/constitution/README.md`, ADR 0016의 이력, `tools/sibling_overlap.py`의 출력이 맞는다
- [x] 이 영역 파일에서 홀로 쓰인 판을 앞뒤 글자와 함께 다시 훑었고(UTF-8, 양성 대조로 남긴 줄이 나옴), 남은 자리가 모두 바꾸지 않는 것이다. 훑은 명령과 결과는 일지에 있다
- [x] 바꾸기 전과 뒤에 시험 이름을 맞대는 곳(변이 표, 프로브, 문서)을 grep했고 옛 이름 잔존이 살아 있는 글에서 0이다
- [x] `uv run pytest`, `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `tools/check_instructions.py`, `tools/check_type_escapes.py`, `tools/plan_table.py --check`가 초록이다
- [x] 셀프 리뷰(`/code-review`)와 PR 직전 리뷰(`bug-perf-review`, `/security-review`)의 Critical·Major를 고쳤고 결과가 일지에 있다

## Comments

- 2026-11-20, 근거. 사용자가 PR 87 병합 보고의 끝에서 홀로 쓰인 판 영역을 이 세션에서 이어 낼지 물은 데 `네, 이어서`라고 답했다(범위는 PR과 병합까지).
- 2026-11-20, 헌법과 PRD 문구 승인. 선택 화면은 헌법 `tech.md`의 11행과 23행, PRD 19행의 판을 버전으로 바꾸고 헌법 버전을 1.5.6에서 1.5.7로 올려도 되는지 물었고, 사용자가 선택지 `바꾼다 (Recommended)`를 골랐다. 그 선택지의 요지: 이미지와 도구에 붙은 번호를 가리키는 말이라 용어집의 버전과 맞추고, 규칙은 그대로이고 낱말만 바뀌는 문구 수정이라 patch로 올리며 까닭은 ADR 0016 이력에 적는다.
