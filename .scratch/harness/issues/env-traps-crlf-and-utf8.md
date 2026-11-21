# env-traps-crlf-and-utf8: 줄 끝 CRLF는 커밋 전 검사가 잡게 하고, `python -I`의 한글 깨짐은 환경 함정에 한 줄 적는다

**What to build:** 대기열 두 항목이 모두 반영 차례(다섯 번째 이상)에 이르렀다. 항목마다 `어디로`가 두 길을 열어 두었고, 이 티켓이 어느 쪽이 맞는지 정한다.

**1. `crlf-from-script-edits`(11회차): 검사로 간다.** 스크립트의 `write_text`나 리다이렉트가 Windows에서 저장소 파일을 CRLF로 바꿨고, 그때마다 `git add`가 내는 `CRLF will be replaced by LF` 경고로야 알았다. 11회차는 어느 단계가 CRLF를 만들었는지도 가리지 못했다. 쓴 도구를 알 수 없으니 스크립트를 쓸 때 줄바꿈을 LF로 둔다는 지침 한 줄로는 막을 수 없고, 작업 사본에 남은 CRLF를 직접 보는 검사가 맞다. `CLAUDE.md` 교정 루프도 린터·훅이 판정할 수 있는 것은 지침이 아니라 도구 설정에 두라고 한다. 그래서 `CLAUDE.md`에는 줄을 더하지 않는다.
- `.gitattributes`가 `* text=auto eol=lf`라서 내 컴퓨터에 있는 파일(작업 사본)이 CRLF인 텍스트 파일은 늘 사고다. 커밋에는 git이 LF로 바꿔 담으므로 손상은 없지만, 바꾸기 전의 작업 사본을 읽는 도구(시험, 훅, 다른 스크립트)는 CRLF를 읽는다.
- 손으로 봤다(커밋하지 않은 스크립트로 `git ls-files --eol`의 파일을 읽었다. 2026-11-21, 이 티켓의 워크트리): CRLF 바이트가 든 추적 파일은 43개이고 전부 앞 8000바이트 안에 NUL(글자가 아닌 0번 바이트)이 있는 이진 파일이다. `evals/public-docs/`의 PDF, HWPX, `.f32`다. 텍스트로 읽히는 추적 파일에는 CRLF가 없다. 그래서 CRLF를 어긋남으로 내도 이 저장소는 초록으로 남는다.
- `tools/check_line_separators.py`가 텍스트 파일의 CRLF를 어긋남으로 낸다. 파일마다 한 줄이다: 첫 CRLF의 줄과 열, CRLF가 든 줄 수(`<줄>:<열>: CRLF 줄 끝 <수>줄`). 922줄짜리 파일이 922줄의 출력을 내지 않게 하려는 것이다. 이 줄에는 ` U+`가 들지 않아 `chr()` 안내는 붙지 않고, 되돌리는 법을 알리는 안내가 따로 붙는다(스크립트가 파일을 쓸 때 줄바꿈을 LF로 두고, 이미 CRLF가 된 파일은 줄 끝의 CR 문자만 지운다). 안내는 원인을 단정하지 않고 "흔한 원인은"으로 쓴다.
- CRLF의 CR을 줄 끝이라 보지 않는다는 모듈 독스트링의 설명을 바꾼다. 홀로 선 CR의 판정(뒤에 LF가 없는 CR)은 그대로다. `separators_in`은 건드리지 않고 CRLF 판정을 `problems_in`에 새 함수로 더한다. `tools/hook_line_separators.py`(Write·Edit 뒤에 편집 직후 알려 주는 훅)는 이번에 바꾸지 않는다: 원인이 적힌 회차는 모두 Bash의 스크립트나 리다이렉트였고 11회차는 원인을 가리지 못했다. 훅의 `못 보는 것`에 CRLF를 적고 이미 있는 시험(`test_홀로_선_CR_은_어느_파일에서나_알리고_CRLF_는_침묵한다`)이 침묵을 고정한다. 훅 시험이 검사와 훅의 자리를 견주는 `test_커밋_전_검사와_같은_문자를_같은_자리에서_본다`는 CRLF 어긋남을 견주는 몫에서 빼고, 왜 빼는지 적는다.
- `.pre-commit-config.yaml`의 `check-line-separators` 훅 이름(커밋 때 화면에 뜨는 글)이 잡는 것을 나열하므로 `CRLF 줄 끝`을 더한다(셀프 리뷰 명세 축이 짚었다).

**2. `python-i-utf8`(7회차): `CLAUDE.md` 환경 함정에 한 줄.** `python -I`는 `PYTHON*` 환경 변수를 읽지 않아 `.claude/settings.json`의 `env`가 넣는 `PYTHONUTF8=1`이 듣지 않는다. 손으로 봤다(이 워크트리의 Bash, 2026-11-21): `uv run python -I -c "import sys; print(sys.flags.utf8_mode, sys.stdout.encoding)"`가 `0 cp949`를, `PYTHONUTF8=1`을 앞에 붙여도 `utf8_mode` 0을, `-I -X utf8`을 붙이면 `1 utf-8`을 냈다. 판정할 도구가 없는 명령줄 습관이라 지침 한 줄이 맞다(막는 훅은 지침이 어겨진 뒤의 일이다, `CLAUDE.md` 교정 루프).

**이번에 바꾸지 않는 것.**
- `control-char-from-script-escape`(날것 C0 제어 문자 검사). 같은 파일이지만 1회차라 다섯 번째에 반영한다. 그때 이 티켓이 더하는 CRLF 판정 옆에 더한다. 이 PR이 그 항목에 한 일은 본문에 주석 한 줄이다: 어디로 줄의 `crlf-from-script-edits`와 한 chore로 묶는다는 말이 이 티켓으로 낡았다는 것.
- `hook_line_separators.py`의 판정. 위에서 적은 까닭으로 둔다. 같은 사건이 편집 도구에서 나면(Write·Edit이 CRLF로 저장) 그때 훅 후보로 올린다.
- `.gitattributes`. 규칙(`eol=lf`)은 맞고, 어긴 작업 사본을 잡는 것이 이 티켓이다.

**대기열:** crlf-from-script-edits, python-i-utf8

**Status:** done

- [x] `tools/check_line_separators.py`가 텍스트 파일의 CRLF를 파일마다 한 줄로(첫 자리와 CRLF 줄 수) 어긋남으로 내고 되돌리는 안내를 붙인다. NUL이 든 이진 파일, 홀로 선 CR의 판정, 보이지 않는 문자의 판정은 그대로다
- [x] `tests/tools/test_check_line_separators.py`가 CRLF 판정(순수 함수, 파일 섞임, CLI 진입점을 subprocess로 한 번)과 이진 파일의 침묵을 고정하고, 옛 테스트의 "CRLF 의 CR 은 잡지 않는다"가 새 뜻으로 고쳐졌다. 빨강에서 시작했다(구현 전에 실패하는 것을 보았다)
- [x] `.pre-commit-config.yaml`의 `check-line-separators` 훅 이름에 `CRLF 줄 끝`이 있다
- [x] `tests/tools/test_hook_line_separators.py`의 검사와 훅 견줌이 CRLF 어긋남을 뺀 몫만 견주고 그 까닭을 적으며, `tools/hook_line_separators.py` 독스트링의 `못 보는 것`에 CRLF가 있다
- [x] 모듈 독스트링이 새 판정과 `못 보는 것`을 담고 옛 문장이 남지 않았다(`CRLF 의 CR 은 줄 끝이라` 잔존 0)
- [x] `CLAUDE.md` 환경 함정에 `-I` 뒤 `-X utf8` 한 줄이 있고 `uv run python tools/check_instructions.py`가 통과한다
- [x] 이 저장소의 추적 파일에 새 판정을 돌려 초록이고(`uv run python tools/check_line_separators.py`), 알려진 빨강(CRLF가 된 임시 파일)으로 종료 1을 손으로 보았다
- [x] `uv run pytest tests/tools`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`가 초록이다
- [x] 대기열 항목 `crlf-from-script-edits`와 `python-i-utf8`의 상태가 닫힘으로 바뀌고 닫힘 줄에 한 것이 적혀 있다
- [x] 일지가 있고 이 PR의 셀프 리뷰 결과를 담는다
