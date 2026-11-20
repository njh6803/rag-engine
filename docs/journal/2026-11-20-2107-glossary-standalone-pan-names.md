# glossary-standalone-pan-names: 하네스·테스트·배포 파일에 홀로 쓰인 판을 버전으로 바꾼다 · 2026-11-20

PR 87(일지 `2026-11-20-1854-glossary-release-number-names.md`)을 병합한 같은 세션이 그 일지 "다음"의 첫째 영역을 이어서 한 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-standalone-pan-names.md`, 브랜치는 `chore/glossary-standalone-pan-names`이고 `origin/dev`(`beef4af`, PR 87까지 든 것)에서 새로 땄다. 용어집의 이름을 agent-os의 결정에 맞추는 일의 열 번째 PR이다. 계기, 한 것, 훑은 것, 검증을 차례로 두고, 셀프 리뷰 이후의 절은 PR을 연 뒤 이어 쓴다.

## 계기

PR 87 보고의 끝에서 사용자에게 홀로 쓰인 판 영역을 이 세션에서 이어 낼지 물었고 "네, 이어서"라고 답했다. 요청 범위는 PR과 병합까지다. 홀로 쓰인 판은 한 PR로 내기에는 크기 때문에 파일 묶음으로 나눴다. 이 PR은 하네스(도구, 스킬, 시험, 워크플로, 설정)와 배포 파일 묶음이고, 나머지(`src/`, 검색 평가 묶음, 용어집, README, 운영 문서, PR 서식)와 색인 판 계열은 마지막 PR이 맡는다.

## 한 것

- 하네스 묶음에서 홀로 쓰인 판(앞이 한글이 아니고 뒤가 정·단·별·매가 아닌 판)을 줄 통째로 뽑아 뜻을 가렸다(스크래치 스크립트로 `git ls-files`의 UTF-8 파일을 훑었다). 뜻이 모두 버전(도구·이미지·액션·옛 구현의 번호)이었고, 그 가운데 파다(掘)의 활용 몇 줄과 남의 결정 이름 인용 한 줄, 색인 판 두 줄은 따로 가려 남겼다.
- 가린 다음 같은 정규식으로 한 번에 바꿨다(`apply_standalone.py`, 파일 77개에서 271곳을 바꿨다). 줄 번호로 건너뛸 줄을 지정했기 때문에 줄 번호가 어긋난 한 곳(`tools/check_instructions.py` 360행의 `손으로 판 워크트리`, 파다의 활용)을 잘못 바꿨고, 바꾼 줄을 뜻별로 다시 훑다가 잡아 되돌렸다. 되돌린 뒤 바뀐 곳은 약 270곳, 파일은 70여 개다.
- 한글을 두 칸으로 세는 린터의 줄 길이에 낱말이 두 글자 늘어 걸린 주석과 독스트링 37곳은 `tools/rewrap_comments.py`로 다시 감았다. 코드 줄은 건드리지 않았다.
- 바꾼 줄에 든 `일지 <날짜>-<번호>` 인용 가운데 이 저장소에 없는 agent-os 일지를 가리킨 열세 줄(번호는 열네 개)은 `tools/sibling_overlap.py`가 어디에도 없는 인용으로 알려서 번호를 코드 스팬으로 감쌌다(도구가 일부러 없는 이름이면 그렇게 하라고 안내한다). 줄을 다시 감으면서 더해진 줄이 바뀌어 새로 걸린 한 곳(`tools/mutate.py`)도 같은 방식으로 감쌌다.
- 헌법 `docs/constitution/tech.md` 두 곳과 `docs/PRD.md` 한 줄(사용자 승인)을 바꿨고, 헌법 버전을 1.5.6에서 1.5.7(patch)로 올렸다. 까닭은 ADR 0016의 이력 2026-11-20에 적었다(본문은 고치지 않았다).
- 대기열 `glossary-plain-names-left`에 이번 영역을 한 문단 더했다. 열린 항목 `renamed-term-reintroduced-by-parallel-pr`는 병합 전에 열린 PR이 옛 낱말을 다시 들여오는지 보라는 것이라, 열린 PR을 확인했다. 열린 PR은 main을 dev에 합치는 PR 85 하나뿐이어서 다시 들여온 곳이 없었고, 회차를 더하지 않았다.
- 사용자 승인: 선택 화면에서 헌법 두 곳과 PRD 한 줄의 변경과 버전 올림에 "바꾼다 (Recommended)"를 골랐다. 원문은 티켓의 `## Comments`에 있다.

## 훑은 것

앞 PR 일지가 정한 모양(일치 지점의 앞뒤 글자, UTF-8, 양성 대조)을 지켰다.

- 바꾸기 전: 추적 파일 가운데 하네스 묶음에서 홀로 쓰인 판을 줄 통째로 찍었다(`survey_group.py`, `harness_lines.tsv`). 양성 대조로 `tools/hook_env_read.py`의 `옛 판` 열 자리가 나왔다.
- 바꾼 뒤: 같은 스크립트를 다시 돌리니 이 묶음에서 83줄 103곳이 남았다. 바꾸지 않는 파일(`GLOSSARY.md`, `README.md`, `compose.eval.yml`, `tools/search_eval.py`, `tests/tools/test_search_eval*`, `docs/constitution/operations.md`, PR 서식, `claude-code-review.yml`)의 줄을 빼면 아홉 줄이 남았고 모두 바꾸지 않기로 한 것이다. 파다의 활용 여섯 줄(아래 일곱째 줄은 되돌린 `tools/check_instructions.py` 360행이다. `.claude/skills/open-session/SKILL.md` 52행, `tests/tools/test_check_instructions.py` 173·266행, `tests/tools/test_hook_worktree_skill_overrides.py` 81행, `tools/hook_payloads.toml` 824행, `tools/tidy_checkouts.py` 91행), agent-os 결정 이름 인용 한 줄(`.github/workflows/release.yml` 442행), 색인 판 두 줄(`tests/tools/test_check_notes.py` 875행, `.claude/skills/code-review/SKILL.md` 108행)이다. `tools/check_instructions.py` 360행의 파다는 되돌렸으므로 이 훑기에는 나오지 않았다. 줄 수는 출력에서 옮긴 값이다.
- 버전으로 바뀐 줄 가운데 파다의 활용이 섞였는지는 diff의 더해진 줄에서 `손으로|직접|폴더에|자리에|이미|따로|새로` 같은 앞말과 `워크트리|것|폴더|구멍|자리|곳|뒤` 같은 뒷말이 버전에 붙은 줄을 모아 눈으로 봤다(`scan_dig.py`). 의심 줄 여든 가량이 모두 첫 버전, 옛 버전, ~던 버전 같은 버전의 뜻이었고 파다는 앞에서 말한 한 곳(`tools/check_instructions.py` 360행)뿐이었다.
- 시험 이름이나 문구를 맞대는 곳: 이 영역은 시험 이름을 바꾸지 않았다(문구는 독스트링과 주석). 변이 표와 프로브 toml이 바뀐 낱말을 맞대는지 `git grep`으로 찾았으나 검색 평가 묶음 밖에서는 없었다.

## 검증

손으로 친 것은 파이프 없이 하나씩 쳤다.

- `uv run ruff check .` 통과(처음에는 줄 길이 37곳이 걸렸고 다시 감은 뒤 통과), `uv run ruff format --check .` 796개 파일 이미 맞음, `uv run pyright` 0 errors, `uv run lint-imports` 2 kept 0 broken, `uv run python tools/check_type_escapes.py`와 `uv run python tools/check_instructions.py` 출력 없음.
- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 이 브랜치의 새 번호는 헌법 1.5.7이고 형제가 쓴 가장 높은 번호는 1.5.6(`origin/dev`). 처음에는 어디에도 없는 일지 인용 열세 줄을 알렸고 코드 스팬으로 감싼 뒤 다시 감기로 줄이 바뀐 한 곳이 더 나와 감싸고 통과했다. 함께 고친 파일로 형제 워크트리 `08-ci-releases-from-main`이 `tests/standalone/test_standalone_compose.py`를 고치고 있다고 알렸다(글자 충돌 후보, 종료 코드와 무관).
- `uv run python tools/plan_table.py --check` 통과.
- 영향이 큰 시험을 한 묶음으로 돌렸다(`tests/tools/test_deploy_guide.py`, `test_release_workflow.py`, `test_check_instructions.py`, `test_check_constitution_version.py`, `test_check_adr_pointers.py`, `test_check_ticket.py`, `tests/standalone`, `tests/test_plan_status.py`). 397건이 통과했고 2건이 실패했다. 둘 다 `tests/standalone`의 Docker 시험이다. `test_MCP_검색_결과에_표본_문서의_문장이…`는 `httpx2.ReadTimeout`이었고 `test_서버_프로세스를_죽이면_컨테이너가_다시_떠_15초_안에_200이다`는 복구에 25.9초가 걸렸다(기준 15초). 이 파일의 변경은 독스트링과 주석 세 줄뿐이고 `deploy/`의 변경도 주석뿐이라 동작을 바꿀 수 없다. 두 건만 다시 돌렸더니 같은 두 건이 또 실패했다(복구 23.8초). 원인은 재지 않았다. 변경이 동작에 닿지 않으므로 시간 시험이 이 PC의 부하에서 빨갛게 나온 것으로 보지만 이것은 추정이다. 이 시험은 기본 pytest에서 빠져 있고(`norecursedirs`) CI의 `standalone` 잡이 돌리므로 그 결과를 PR의 CI에서 본다. `test_check_ticket.py`는 처음 한 묶음에서 임시 원격 푸시 준비가 실패했으나 단독으로 124건 통과했다. 전체 pytest와 나머지 훅은 커밋이 부르는 pre-commit의 검사 러너가 돈다.
- 첫 커밋 시도의 전체 pytest는 4933건 통과, 1건 실패였다(969초). `tests/test_serve_command.py`의 서버가 뜨면 JSON Lines만 남기는 시험이 두 번째 요청에서 `httpx.ReadTimeout`을 냈다. 이 변경은 `src/`에 닿지 않는다. 그 파일만 단독으로 다시 돌렸을 때 첫 실행은 같은 `ReadTimeout`으로 실패했고 둘째 실행은 2건 모두 통과했다(11.7초). 부하에서만 빨간 시간 시험의 새 사례로 보고, 사용자가 이 종류를 닫아 두었으므로 항목에 잇지 않고 여기에만 적는다. 커밋을 다시 쳤다.

## 셀프 리뷰

`code-review` 스킬로 기준 `beef4af`(`origin/dev` 끝)에서 수정 76개 파일, 미추적 2개(티켓, 일지), 커밋 0개를 두 축으로 봤다. 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical은 없었고 표준 축이 Major 하나를 냈다.

**고친 것.**
- 표준 축 Major. ADR 0016 새 이력과 티켓이 이미지와 도구에 붙은 번호를 가리키는 말이라 용어집의 버전 항목에 든다고 적었으나, 용어집의 버전 항목은 계약과 헌법의 번호만 풀이하고 릴리스 항목은 버전을 피할 말로 둔다(버전 태그만 예외). 거짓 문장이었다. 이력은 항목을 넓히는 일을 용어집을 바꾸는 마지막 영역에 맡긴다는 말로 고쳤고 티켓 첫 문단에도 같은 말을 넣었다.
- 표준 축 Minor. 파일이나 색인의 시점 사본을 뜻하던 판(`main 의 판`, `부모 판`, `커밋에 들 판(색인)` 따위 약 60곳)도 버전으로 바뀌어 번호와 한 글 안에서 섞였다. 가장 나빴던 구절 `커밋에 들 판(색인)`은 `tools/check_constitution_version.py`, `tools/mutate.py`, 그 시험들, `.pre-commit-config.yaml`에서 내용으로 적었다. 나머지는 자연스러운 말이라 버전으로 두었고 티켓의 고치는 곳에 그 사실을 적었다. 명세 축도 같은 구절이 파일마다 버전과 내용으로 갈렸다고 짚어, `tools/mutate.py`와 그 시험까지 맞췄다.
- 표준 축 Minor. 시험 함수 이름 아홉 개를 바꿨는데 티켓이 식별자는 바꾸지 않는다고 했다. 옛 이름 조각은 저장소에 참조가 없어 티켓에 함께 바꿨다고 적었다.
- 표준 축 Nit. `tools/tidy_checkouts.py`에서 줄이 갈린 일지 인용 한 곳에 백틱이 빠져 있었다(`sibling_overlap`은 줄을 가른 인용을 보지 못한다). 감쌌다.
- 명세 축 Minor. 이력이 세 곳이라 적은 셈이 파일 3개 줄 6개와 맞지 않았다. 구절 이름으로 고쳐 적었다.

**남긴 것과 이유.** 없음.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장).**
- ADR 0016 이력: 용어집의 버전 항목은 아직 계약과 헌법의 번호만 풀이하므로 이미지와 도구의 번호까지 넓히는 풀이는 마지막 영역에 맡긴다.
- ADR 0016 이력: 파일이나 색인의 시점 사본을 뜻하던 판은 구절 `커밋에 들 판(색인)`만 내용으로 적었다.
- 티켓: 약 60곳이 시점 사본을 뜻했고 시험 함수 이름 아홉 개를 함께 바꿨다.

**다시 돌린 명령.** `uv run ruff check .`과 `uv run ruff format --check .`는 통과했다. 나머지는 아래 "커밋"의 pre-commit 결과가 갈음한다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 거부되어(앞 PR들과 같다) 보안 축은 내장 `/security-review`의 방식으로, 버그·성능 축은 `bug-perf-review` 에이전트로 대신했다.

**보안.** 지적 없음. 스킬이 넘겨받는 diff 칸이 작업 트리가 커밋 전이라 비어 있어, 보안과 닿는 파일(`.github/workflows/ci.yml`, `release.yml`, `zizmor.yml`, `.pre-commit-config.yaml`, `tools/hook_payloads.toml`, `.claude/rules`, `.claude/agents`)의 변경분을 `git diff -U0`로 직접 읽었다. 워크플로에서 바뀐 것은 주석뿐이고 `run`, `if`, `env`, `permissions`, 비밀 값 참조, 표현식은 그대로다. 훅 설정에서 바뀐 것은 표시 이름과 설명 문자열(`note`)뿐이고 `contains`와 정규식은 그대로다.

**버그·성능(`bug-perf-review`).** 유효 2, 오탐 0. Critical·Major 없음. 이전과 이후 파일을 단어 단위로 맞댔고(백틱, 주석 표지, 공백 차이는 무시) 76개 파일에서 판이 버전이나 내용으로 바뀐 것 말고 달라진 단어는 헌법 버전 숫자, ADR 이력 항목, 대기열 문단뿐이었다. 시험 함수 이름 아홉 개가 `tests/` 전체에서 중복되지 않고 옛 이름 조각이 남지 않았다. `tools/mutate.py`의 `_BROKEN_HERE`와 `tests/tools/test_mutate.py`의 `_깬_커밋`은 같은 문자열이다. 밀 주장(ADR 0016 이력과 티켓의 숫자와 인용)도 맞았다.

**고친 것.**
- Minor. ADR 0016 이력의 괄호 문장이 시점 사본을 뜻하던 판이 모두 내용이 된 것처럼 읽혔다. 실제로는 약 60곳이 버전이고 구절 `커밋에 들 판(색인)`만 내용이다. 그렇게 고쳐 적었다.
- Minor. 일지가 센 파다 뜻의 판은 여섯 줄이 아니라 일곱 줄이고(되돌린 `tools/check_instructions.py` 360행 포함), 파일 수 76개는 이름을 바꾼 파일의 수가 아니었다. 일지의 숫자를 고쳤다.

**남긴 것.** 없음.

**다시 돌린 명령.** 고친 글은 문서뿐이다. 아래 "커밋"의 pre-commit 결과가 갈음한다.

## 커밋

브랜치 `chore/glossary-standalone-pan-names`에서 커밋 `68d788e`(제목 `chore: 홀로 쓰인 판을 버전으로 바꾼다 (harness glossary-standalone-pan-names)`)를 냈다. 78개 파일에서 429줄을 더하고 308줄을 지웠다. 시도는 세 번이었다.

- 첫 시도: 전체 pytest가 4933건 통과, 1건 실패였다(1009초). 실패는 위 "검증"에 적은 `tests/test_serve_command.py`의 `ReadTimeout`이고, 그 파일만 다시 돌리니 통과했다.
- 둘째 시도: 같은 PC에서 다른 세션들이 전체 스위트를 동시에 돌리고 있어 병렬 시험 일꾼(xdist)이 `MemoryError`로 죽었다(빈 메모리가 32GB 중 3GB까지 내려간 때가 있었다). 이 변경의 문제가 아니라서 다른 스위트가 끝나기를 기다렸다가 다시 쳤다.
- 셋째 시도: 통과해 커밋이 만들어졌다.

커밋 제목은 처음 쓴 것이 78자라 커밋 전에 훅이 막았고, 72자 안으로 줄여 다시 썼다. `git push -u origin chore/glossary-standalone-pan-names`는 `origin/dev`(`beef4af`)를 이미 품은 상태여서 그대로 올라갔다.

## PR 봇 회차

PR 90을 `dev`로 열고 마지막 푸시 뒤에 `@coderabbitai review`를 남겼다. 대기(`tools/wait_ci.py 90`) 결과는 헤드 `68d788e`에서 모든 검사가 통과였다(`python`, `image`, `ticket`, `standalone`, `eval-fast`, `eval-full`, `verify`).

- claude-review: 첫 회차에 지적 없음. 표준과 경계 두 축을 봤고, 문자열이 바뀐 `tools/mutate.py`와 `tests/tools/test_mutate.py`의 짝이 맞는다고 확인했으며, 제목 접두 `chore:`에 느낌표가 없는 것도 기준에 맞다고 했다.
- CodeRabbit: `Review rate limited`(무료 리뷰 한도, 다음 리뷰는 약 55분 뒤)로 리뷰가 없었다. 한도에 걸린 것은 통과로 세는 규칙대로 기다리지 않았다. 리뷰를 받은 커밋은 없다.
- CI의 `standalone` 잡이 초록이다. 로컬에서 빨갛게 나온 `tests/standalone`의 Docker 시험 둘은 CI에서 재현되지 않았고, 따라서 로컬의 복구 시간 초과는 이 PC의 부하 때문이었을 가능성이 크다(추정이며 원인을 재지는 않았다).

반영할 지적이 없어 고친 커밋은 없다. 보류한 지적도 없다.

## 회고

후보 3개를 냈고 판정은 승인 0, 기각 3, 넘김 0이다. 일지와 이 세션을 읽었고, 대기열은 `uv run python tools/queue_open_rows.py`로 읽었다(열린 항목 71개, 만료할 항목 없음).

- 후보 1. 건너뛸 줄을 줄 번호로 지정한 일괄 바꾸기가 어긋나 파다(掘) 뜻의 판을 잘못 바꿨다(`tools/check_instructions.py` 360행). 기각. 스크래치 스크립트에서 난 사건 하나이고, 바꾼 줄을 뜻별로 다시 훑는 절차가 이미 잡아 되돌렸다. 저장소에 올릴 검사가 없다.
- 후보 2. 커밋 제목이 78자라 길이 기준을 넘었다. 기각. 커밋 전에 훅이 막았으므로 이미 있는 훅이 그 자리에서 알린 것이다. `commit-msg-after-slow-checks`에 회차를 더하지 않는다.
- 후보 3. 커밋 시도마다 전체 pytest가 부하에서만 빨갛게 나왔다(`ReadTimeout`, 동시 스위트로 인한 `MemoryError`). 기각. 부하 시간 시험 종류는 사용자가 2026-11-15에 닫아 두었으므로 새 사례는 일지에만 적는다.

티켓의 대기열 줄에 든 `renamed-term-reintroduced-by-parallel-pr`는 병합 전에 열린 PR이 옛 낱말을 다시 들여오는지 보는 항목이다. 작업 중에 열린 PR을 확인했을 때는 main을 dev에 합치는 PR 하나뿐이어서 다시 들여온 곳이 없었고, 병합 직전에 `tools/sibling_overlap.py`로 한 번 더 본다. 이번 세션에서 회차를 더한 항목은 없다. 반영한 것도 없어서 티켓에 `회고 반영` 줄을 더하지 않았다.

## 다음

병합은 이 세션이 이어서 한다. 병합 직전에 `git fetch origin`과 `git merge-base --is-ancestor origin/dev HEAD`로 뒤처졌는지 보고, `tools/sibling_overlap.py`와 `headRefOid` 대조를 거친다. 병합 결과(`주 체크아웃 미갱신` 한 줄 포함)는 일지가 아니라 병합 보고에 적는다.

용어집 이름 맞추기에 남은 일은 아래와 같다.

1. 별도 작은 PR: `.github/workflows/claude-code-review.yml`의 21행과 87행에 남은 판 둘. 이 워크플로를 바꾸는 PR은 일지·티켓·프로브 밖의 파일을 함께 실을 수 없어서 이 PR에서 뺐다.
2. 마지막 영역 PR: `src/`, 검색 평가 묶음(`tools/search_eval.py`, `tests/tools/test_search_eval*`, `compose.eval.yml`), 색인 판 계열(이 PR에서 남긴 두 줄 `tests/tools/test_check_notes.py` 875행과 `.claude/skills/code-review/SKILL.md` 108행 포함), `GLOSSARY.md`(버전 항목을 이미지와 도구의 번호까지 넓히는 풀이, 버전 칸 예외), `README.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/constitution/operations.md`. 사용자가 색인 판은 버전으로 바꾼다를 이미 골랐다.
3. 대기열 `glossary-plain-names-left`(사람 몫)에는 이 영역을 한 문단 더해 두었다. 남은 영역이 끝나면 닫는다.
4. 이 세션의 정리 남은 일: `tidy-checkouts` 때 거부된 `remove-branch worktree-04-install-guide-walks-operator`, 건너뛴 `empty-trash`, 넘긴 `14-reindex-version-switch` 워크트리. 테스트용 PostgreSQL 컨테이너(`rag-engine-test-postgres-1`)는 켜 둔 채다.
