# search-eval 02: 묶음 형식과 `validate`의 파일 검사 · 2026-11-13

티켓 `.scratch/search-eval/issues/02-eval-set-format-validate.md`를 구현한 기록이다. 브랜치는 `feature/02-eval-set-format-validate`이고, `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 먼저 돌고 `EnterWorktree`로 새 워크트리에 들어가 했다. 세션 도중 컨텍스트가 한 번 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 02, 명세 `.scratch/search-eval/spec.md`의 "평가 세트의 형식"·"날짜와 시각의 형식"·"자리와 층", 앞 일지 `2026-11-13-2245-search-eval-01-ports.md`의 `## 다음`, 선례 `adapters/ingest_command.py`(`_collect`), `adapters/blob_store.py`.
- `tidy-checkouts` 결과(보고만 하고 답을 기다리지 않았다): 루트는 `dev`(97f9914)이고 커밋하지 않은 로그 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 당기지 못했다. 병합된 워크트리 정리 가운데 `14-reindex-version-switch`는 사람에게 넘겼고 `.claude/worktrees/.tidy-trash/`에 `.venv` 넷이 남았다.

## 한 것

- `domain/eval_set.py`: 묶음의 값(`EvalSet`, `EvalDocument`, `EvalConfig`, 기대 근거 `PassageEvidence`·`PageEvidence`, `EvalQuery`, `EvalFilter`, `MissReview`, `EvalProblem`)과 상수(지원하는 판의 major 1, 문서 파일의 합 30MB, 유형 표지 넷, 놓침 까닭 다섯).
- `app/check_eval_set.py`: 파일을 열지 않고 값만 보는 목록 판정. 중복 `key`와 `id`, 빈 기대 근거, 모르는 유형 표지, 목록에 없는 문서, 한 질의 목록 안의 같은 `evidence_id`, 짝이 없는 `evidence_id`, `groups`가 든 필터, 기대 근거의 문서를 거르는 기간 필터(`updated_after` 포함, `updated_before` 제외), `miss-review`의 참조와 까닭.
- `adapters/bundle_paths.py`: 경로 판정 한 자리. 글자만 보는 거부(절대 경로, 역슬래시, `..`, 정규 꼴이 아닌 경로)와 링크를 푼 결과가 기준 폴더 안인지 보는 거부. `under=`로 `documents/` 같은 하위 폴더 기준도 판정한다.
- `adapters/eval_set_reader.py`: `kst_midnight`(날짜를 그날 00:00 `+09:00`로), `read_eval_set`. pydantic 모델(`extra="forbid"`, strict)로 읽고, 독립인 파일의 오류는 모아 낸다. 오류 문장에는 칸 위치와 메시지만 싣는다.
- `adapters/eval_bundle_files.py`: 문서 파일의 존재·sha256(소문자 16진, 글자 그대로)·합 30MB 초과(정확히 30MB는 통과)·`documents/`의 목록에 없는 파일과 링크, 머리가 가리키는 파일 모두와 `records/`의 경로 판정. `os.scandir`로 직접 걷고 링크와 junction은 내려가지 않는다.
- `adapters/eval_validate.py`: 읽기 오류면 그 오류만, 아니면 두 판정을 합친다. `tools/search_eval.py`: argparse 하위 명령 `validate <묶음 폴더>`, 종료 코드 0·1·2.
- `README.md`의 트리, `.scratch/plan-head.md`의 목표 배치(와 생성 파일 `.scratch/plan.md`)에 새 모듈과 `tools/search_eval.py`를 더했다.
- 시험(79개): `tests/tools/test_search_eval.py`(55, `main(argv)`로 규칙마다 종료 코드와 까닭 문구를 본다. 윈도 junction과 리눅스 심볼릭 링크로 링크 시험을 짓고 skip하지 않는다), `tests/adapters/test_eval_set_reader.py`(8), `tests/app/test_check_eval_set.py`(16), 지원 `tests/support/eval_bundle.py`.
- 변이 표 `.scratch/search-eval/probes/eval_set_validate_mutations.toml`(27). 구현과 함께 써서 빨강을 본 적 없는 경계 시험을 겨눈다.

## 정한 것

- `documents/` 안의 링크는 묶음 안을 가리켜도 오류로 낸다. 문서는 실제 파일이어야 하고 걷기가 링크 안으로 내려가지 않기 때문이다. `BundlePaths` 자체는 안을 가리키는 링크를 받는다(선례 `ingest_command._collect`와 같다). 명세는 밖을 가리키는 링크만 말한다. 티켓 `## Comments`에 적었다.
- 읽기 오류가 나면 거기서 멈추고 목록 판정은 하지 않는다. 머리가 틀리면 다른 파일의 이름도 알 수 없기 때문이다. 독립인 파일(`config.json`, 문서 목록, 기대 근거, 질의 목록, `miss-review.jsonl`)은 한 파일이 틀려도 나머지를 읽어 오류를 함께 낸다.
- `documents.json`의 `bytes` 칸은 읽기만 하고 실제 크기와 견주지 않는다. 해시가 내용을 가르고 명세의 `validate` 목록에 없다.

## 셀프 리뷰

`code-review` 두 축, base `50ebe47`(커밋 0개, 추적 변경 4개, 미추적 12개). 표준 축은 Sonnet 5.5 / high다. Critical과 Major는 없었다.

- 고친 것(표준 축 Minor): `tests/tools/test_search_eval.py`의 마지막 단언 `"숨은.docx" not in capsys.readouterr().err`가 `_rejected`가 버퍼를 이미 비워서 항상 참이었다. `_rejected`가 표준 오류를 돌려주게 했다. `test_문서_key가_documents_안이_아니면_거부한다`는 이름과 달리 `..` 글자 검사만 밟았다. 이름을 맞추고, `documents/` 안의 링크가 묶음 안의 `documents/` 밖을 가리키는 경우를 가르는 시험을 새로 더했다(`resolved.is_relative_to(base)`를 `self._root`로 바꾸는 변이에서 빨강). `records.iterdir()`가 `OSError`를 잡지 않아 권한 없는 `records/`에서 트레이스백으로 죽었다. 잡아서 `records: 폴더를 읽을 수 없다`로 낸다(시험 하나, 변이 하나).
- 고친 것(Nit과 명세 축 (c)): `\d`가 전각 숫자를 받아 `２０２６-01-15`가 "달력에 없는 날이다"로 보고됐다. `[0-9]`로 고치고 시험을 더했다. 첫 시험은 `match="꼴이어야 한다"`가 달력 오류의 문구에도 있어 `\d`로 되돌린 변이에서 초록이었다. 변이로 알아내 문구 전체를 맞춘 시험으로 바꿨다(변이 19, 이제 빨강). `_problems` 독스트링의 "입력한 값은 싣지 않는다"는 판별 태그의 값과 모르는 칸의 이름이 pydantic 메시지에 실리므로 "질문과 글귀 같은 입력한 값은 싣지 않는다"로 좁혔다. `test_eval_set_reader.py` 독스트링이 경계 시험 전체가 `kst_midnight`를 거친다고 적은 것을 CLI 시험만 그렇다고 고쳤다. README의 `tests/tools/` 줄에 `validate` 시험을 더했다.
- 남긴 것(Minor·Nit, 동작에 영향이 없다): `eval_bundle_files.py`의 `"config.json"`·`"miss-review.jsonl"`이 `eval_set_reader.py`의 상수와 같은 지식의 중복이다. `check_eval_set.py`가 오류 위치를 `"documents.json"`과 `"evidence.jsonl"`로 박아 둔다(머리가 정하는 파일 이름이다). `_review_problems`가 `check_eval_set`이 이미 만든 `evidence` 맵을 쓰지 않고 선형 탐색한다. `BundlePaths`와 `eval_bundle_files`의 단위 시험이 `tests/adapters/`에 없고 CLI로만 시험한다(`.claude/rules/tests.md`는 `tests/tools/`를 `tools/`의 순수 함수 시험용으로 둔다). `key`가 `documents/a.docx`면 `documents/` 접두를 안내하지 않는다. 변이 표의 표지 둘(`역슬래시가 들었다`와 같은 윈도 경로 문구)이 윈도의 경로에서만 난다. 모두 02의 범위를 넘거나 후속 정리로 둔다.
- 다시 돌린 것: `uv run ruff check .`와 `uv run ruff format --check .`(0), 고친 시험 셋(68 passed), 변이 17·18·19(기대대로 빨강).

## PR 직전 리뷰

CodeRabbit CLI가 한 번 돌았고(`--include-untracked`, 미추적 열네 파일 포함) 리뷰는 끝까지 돌았다(`Seat: not assigned`, findings 4). 보안 축으로 내장 `/security-review`도 돌았고 확신도 8 이상의 지적은 없었다. 서브에이전트가 재현으로 더한 것을 합쳐 여덟 건을 트리아지했다.

- 고친 것(Major 둘): `_parse_lines`가 `str.splitlines()`로 가르면 JSON 문자열 안의 U+2028·U+0085도 줄 경계가 되어 올바른 줄이 둘로 쪼개져 거부됐다(재현했다). `\n`으로만 가르고 끝의 `\r`을 벗기게 했다(변이 20). 윈도 예약 장치 이름(`CON`, `NUL`, `COM1`과 확장자가 붙은 꼴)이 경로 판정을 지나, 머리의 파일 칸에 `CON`을 적은 묶음이 `validate`를 멈추게 했다(재현했다. `read_bytes()`가 돌아오지 않았다). 마디의 장치 이름과 `:`(대체 데이터 스트림)를 운영체제와 무관하게 글자로 거르고(변이 21·22), `_read_text`가 열기 전에 일반 파일인지 본다(폴더나 FIFO, 변이 23).
- 고친 것(Minor): `_entries`가 `os.scandir`의 `OSError`를 삼켜 읽지 못한 `documents/`가 "문제 없음"으로 끝났다. 폴더가 없는 경우만 조용히 하고 나머지는 `documents: 폴더를 읽을 수 없다`로 낸다(변이 24). `_check_document`의 `is_file()`과 `_read_miss_reviews`의 `exists()`도 `OSError`를 문제로 낸다(이 둘은 시험으로 고정하지 않았다). 판 꼴의 정규식이 4300자리를 넘는 수에서 `int()`로 죽는 길을 `{1,9}`로 닫았다(변이 25). `under=`를 준 판정의 문구가 "묶음 폴더 밖"으로 나가던 것을 "`<under>/` 밖"으로 고쳤다(변이 26). `records` 문제 문구에서 까닭을 권한으로 단정하던 말을 뺐다.
- 보류(Minor): `miss-review`의 `evidence_id`가 그 질의 목록의 질의에 드는지를 보지 않는다. 명세의 `validate` 목록에 짝을 요구하는 말이 없어 판정을 더하는 일이라 건드리지 않았다. 사용자가 정한다.
- 오탐: CodeRabbit이 Critical로 낸, pydantic 메시지를 그대로 싣지 말라는 지적. 재현해 보니 모르는 칸의 이름과 판별 태그의 값은 실리고 입력한 값(정수 칸에 넣은 문자열, 깨진 JSON의 글, 뒤에 붙은 글)은 실리지 않았다. 칸 이름과 태그 값은 질문·글귀·연결 정보가 아니라 원칙 V의 대상이 아니고, 독스트링이 이미 그 한계를 적었다.
- 사실 문장 검증: `_problems` 독스트링, 전각 숫자, 티켓 `## Comments`의 `documents/` 링크와 `bytes` 문장은 참이었다. `BundlePaths`가 안을 가리키는 링크를 받는다는 말에는 `documents/` 자체가 묶음 안의 다른 폴더를 가리키는 링크여도 받아 그 폴더를 문서 폴더로 걷는 것까지 든다는 단서가 붙어 티켓 `## Comments`에 더했다. 하드 링크는 판정이 가르지 못한다는 것을 `bundle_paths.py`의 못 보는 것에 더했다.
- 이 반영이 새로 쓴 사실 문장(PR 봇이 겨냥할 것): `bundle_paths.py` 독스트링의 장치 이름·`:` 서술(윈도에서 열면 읽기가 돌아오지 않거나 장치로 간다는 말, "하드 링크는 …가르지 못한다", "파일 아닌 것(폴더, POSIX의 FIFO)은 … 읽는 쪽이 연 파일인지 보고 거른다"), `_parse_lines` 독스트링("`splitlines()`는 U+2028 같은 문자도 줄 경계로 읽어 …"), `_VERSION_FORM` 주석(4300자리를 넘는 수는 `int()`가 오류로 죽는다는 말), 티켓 02 `## Comments` 넷째~여섯째 항목.
- 다시 돌린 것: 변이 표 전체 26개가 기대대로 빨강, 변경한 시험 셋 78 passed.

## 봇 회차

PR #40, 첫 푸시 fba09c2. 두 봇 모두 첫 회차다(CodeRabbit은 `@coderabbitai review` 뒤에 리뷰했다. 검사 여섯은 모두 초록).

- 고친 것(CodeRabbit Minor): 링크가 서로를 가리키면 `Path.resolve()`가 `RuntimeError`를 내고 `BundlePaths.resolve`가 잡지 못해 `validate`가 오류 보고 없이 traceback으로 끝난다는 지적이다. 윈도 junction 순환(`a`→`b`→`a`)으로 재현했고(Python 3.12.10에서 `Path.resolve()`와 `BundlePaths.resolve()` 모두 `RuntimeError: Symlink loop`), 리눅스도 같은 길로 읽힌다(3.12.10의 `pathlib.py`를 읽었다. `resolve()`는 비엄격 모드에서도 끝에 `stat()`을 불러 `ELOOP`이면 `RuntimeError`를 낸다. 리눅스에서는 돌려 보지 않았다). `resolve`가 `RuntimeError`를 `BundlePathError`(`링크가 순환한다`)로 바꾸고 시험 `test_서로를_가리키는_링크_폴더는_순환으로_거부한다`와 변이 27을 더했다. 변이를 넣으면 그 시험 하나만 빨강이었다(기준선 55 passed).
- 보류(Critical, 검증되지 않음 표시, CodeRabbit): 오류의 메시지와 위치에서도 입력 내용을 제거하라는 지적이다. PR 직전 리뷰에서 같은 지적을 재현해 오탐으로 판정했다. 입력한 값(정수 칸에 넣은 문자열, 깨진 JSON의 글, 뒤에 붙은 글)은 실리지 않고, 모르는 칸의 이름과 판별 태그 값만 실린다. 그것은 묶음의 주인이 쓴 칸 이름이고 질문·글귀·연결 정보가 아니라는 판정은 그대로다.
- 보류(Minor, CodeRabbit): 변이 표의 절대 경로 변이 표지(역슬래시 오류 문구)가 리눅스에서는 나오지 않는다는 지적이다. 맞다. 절대 경로 검사를 끄면 리눅스에서는 푼 경로 판정의 문구가 나온다. 변이 표는 개발 기계(윈도)에서 돌리는 도구라 지금은 고치지 않는다. 두 플랫폼 모두에서 나오는 문구를 고르려면 리눅스에서 변이를 돌려 봐야 한다.
- 보류(Minor, claude-review): `_read_text`의 `raise _fail(...)`가 `try` 안에 있다는 지적이다. `_fail`이 내는 `EvalSetFormatError`는 아래 `except OSError`에 잡히지 않아 동작은 맞다. 밖으로 빼면 변이 24가 겨누는 한 줄(`if path.exists() and not path.is_file():`)의 흐름이 바뀐다. 스타일 문제라 같은 파일을 다시 넓힐 때 정리한다.
- 보류(Minor, claude-review) 둘: `_read_miss_reviews`·`_read_text`·`_check_document`가 같은 모양의 실패 분기를 되풀이한다는 것과, `BundlePaths`·`eval_bundle_files`의 어댑터 단위 시험이 없다는 것이다. 둘 다 이 PR 본문이 남긴 위험으로 밝혔고 아래 "다음"에 있다.
- 보류(Nit, claude-review): `bytes` 칸이 내장 `bytes`를 가린다는 지적이다. `bytes`는 명세 "공공 문서 묶음"이 정한 `documents.json`의 칸 이름이고 형식의 일부라 바꾸지 않는다.

## 검증

- 손으로 친 것: `uv run ruff check .`(0), `uv run ruff format --check .`(0), `uv run pyright`(0 errors, 반영 전), `uv run lint-imports`(2 kept), `uv run python tools/run_checks.py`(반영 전 전체가 종료 코드 0), `tools/mutate.py`로 변이 26 모두 기대대로 빨강(처음 16 가운데 어긋난 둘은 짐작한 표지가 틀린 것이고 시험은 빨강이었다), `tools/sibling_overlap.py`(번호·파일 겹침 없음).
- 반영 뒤: `uv run ruff check .`(0), `uv run ruff format`, 시험 셋 78 passed, `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), `uv run python tools/sibling_overlap.py`(겹침 없음).
- 반영 뒤 `uv run python tools/run_checks.py`는 pytest만 빨강이었다(3924 passed, 1 failed, 305초). 실패는 `tests/server/test_admin_api.py::test_작업_목록은_최근_순이고_상태_한도_커서를_따른다`의 `ingest` 요청이 `httpx.ReadTimeout`으로 끝난 것이고 이 변경이 손댄 파일과 닿지 않는다. 같은 파일을 단독으로 다시 돌리면 16 passed(37초)였다. 부하가 큰 전체 실행에서만 난 시간 초과로 보지만 원인은 재 보지 않았다. 이 사건 하나는 고침도 규칙도 아니라 회차로 세는 후보다(아래 회고 8). 커밋 63f3863의 pre-commit이 전체 pytest를 다시 돌았고 초록이었다(376초, 이 시험 포함. 러너의 나머지 검사 아홉도 초록). 같은 시험이 연속으로 빨강이 아니라서 diagnosing-bugs로 가지 않았다.

## 회고

낸 후보 여덟. 승인 2, 기각 6, 넘김 없음.

1. 변이 표의 표지를 짐작으로 적어 처음 16 가운데 둘(8번 오프셋, 11번 링크)이 어긋났고, 새 변이 셋을 더했을 때 17번 표지가 다시 어긋났다. 어긋난 번호만 다시 돌려 한 바퀴를 줄였지만 표지는 실제 출력을 본 뒤에야 고를 수 있었다. → 승인(회차로 세는 것). 열린 항목 `mutate-marker-discovery`가 이미 처방한 사건이다. 승인 줄을 3회차로 고쳤다. 5회차 전이라 반영하지 않는다.
2. 워크트리에서 검사 출력을 `../../../scratch_gate.log`로 리다이렉트해 주 체크아웃의 루트에 파일을 만들었다(곧바로 지웠고 잃은 것은 없다). `hook_bash_cd_outside`는 `cd`만 보아 이 길을 못 막았다. → 승인(더하는 것). 층은 훅이고 PR 하나로 되돌릴 수 있다. 대기열에서 같은 일을 다룬 항목을 `--search 워크트리.*밖`, `상대.경로`, `cd.outside`로 찾았으나 없어 새 항목 `redirect-outside-worktree`를 1회차로 썼다. 손상이 아니라 5회차 전이라 반영하지 않는다.
3. 시험의 항상 참인 단언(`capsys`가 비어 있는 버퍼를 읽음)과 문구가 겹쳐 두 까닭을 못 가르는 `match`. 앞의 것은 셀프 리뷰 표준 축이, 뒤의 것은 변이 도구가 잡았다. → 기각. 리뷰가 잡도록 둔 기준(`CODING_STANDARDS.md`의 테스트가 행동을 검증하는가)을 어겨 리뷰가 잡은 사건은 제 몫을 한 것이고, 단언이 항상 참인지 가르는 검사는 거짓 양성 없이 짓기 어렵다.
4. `git -C <루트>`와 명령 치환이 든 복합 git 명령이 워크트리 가드에 거부됐다. → 기각. 이미 있는 가드가 그 자리에서 막았다.
5. 파이프가 든 pytest 명령의 종료 코드 경고와 한국어가 아닌 중간 문장 경고가 훅에서 왔다. → 기각. 이미 있는 훅이 그 자리에서 알렸고 따랐다.
6. 셀프 리뷰 두 축이 못 본 Major 둘(`splitlines()`가 U+2028에서 줄을 쪼갠다, 윈도 장치 이름 `CON`이 읽기를 멈춘다)이 PR 직전 CodeRabbit CLI 단계와 그 서브에이전트의 재현에서야 나왔다. → 기각. 리뷰 파이프라인의 PR 직전 층이 제 몫을 한 것이고, 거르는 입력 목록은 도구 하나로 닫을 수 없다. 같은 꼴(경로를 다루는 코드의 윈도 특수 이름)이 다시 나오면 회차로 세는 후보다.
7. 첫 변이 기준선 pytest가 65초, 그 뒤 같은 시험이 2.7초였다(첫 실행의 일시적 지연). → 기각. 사건 없이 떠올린 것이다.
8. 러너 전체 pytest에서 `test_admin_api`의 `ingest` 한 건이 `httpx.ReadTimeout`으로 빨강이었고 단독 재실행은 초록이었다. → 기각. 대기열과 일지에 같은 시험의 기록이 없어 첫 관측이고, 시험 코드나 이 변경 탓이라는 증거도 없다. 같은 시험이 다시 시간 초과로 빨강이면 그때 회차로 센다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 두 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차)뿐이고 이 브랜치와 닿지 않는다.

## 다음

- 이 PR이 병합되면 티켓 02는 끝이고 03(`index`)이 열린다. 03은 `adapters/eval_set_reader.py`의 `kst_midnight`와 `read_eval_set`을 쓴다(티켓 02 `## Comments`).
- 07과 12가 묶음에 쓸 때는 `BundlePaths.resolve`를 지난 경로만 연다(티켓 02 `## Comments`).
- Minor로 남긴 것(상수 중복, 오류 위치 이름 하드코딩, `_review_problems`의 선형 탐색, `tests/adapters/`의 `BundlePaths`·`eval_bundle_files` 단위 시험, `_read_miss_reviews`·`_read_text`·`_check_document`의 되풀이되는 실패 분기, `_read_text`의 `try` 안 `raise`)은 같은 파일을 다시 넓힐 때 정리한다.
- 변이 표의 표지 둘(절대 경로 변이의 역슬래시 문구 등)이 윈도에서 본 출력이라 리눅스에서 그 변이를 돌리면 표지가 다를 수 있다. 리눅스에서 변이를 돌려 두 플랫폼 모두에서 나오는 문구로 고친다(PR 봇 회차의 CodeRabbit Minor).
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이고 커밋하지 않은 로그 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 당기지 못했다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다.
- 사람에게 넘긴 정리: 워크트리 `14-reindex-version-switch`와 `.claude/worktrees/.tidy-trash/`의 `.venv` 넷(다음 정리가 다시 본다).
