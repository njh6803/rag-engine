# release-image 02: 도구가 다음 릴리스 번호와 릴리스 노트와 배포 파일 묶음을 짓는다 · 2026-11-19

release-image 티켓 여덟 가운데 셋째로 구현한 티켓(`02-tools-compute-release-number-notes-bundle`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/02-tools-compute-release-number-notes-bundle.md`이고 브랜치는 `feature/02-tools-compute-release-number-notes-bundle`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, PR 직전 리뷰, 커밋, 봇 회차, 회고, 다음을 차례로 둔다.

## 준비

- 지시문대로 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 맞췄다. 주 체크아웃은 갱신하지 않았다(`tidy-checkouts`는 이 묶음의 첫 세션 몫이다).
- 06이 남긴 일을 이 티켓이 맡았다. `tools/release.py`가 `PRODUCT_PATHS`를 들이면 `operations.md`의 제품 변경 경로 목록을 그 도구를 가리키는 한 줄로 줄이는 일이다. 사용자에게 줄이는 문장의 초안을 보이고 "승인한다"를 받았다.
- agent-os의 `tools/release.py`와 `tests/tools/test_release.py`(커밋 `1aac0cf`)가 옮길 원본이다. 작업 중에 `origin/dev`가 PR #75와 #76만큼 앞서 헌법 판이 1.5.1이 됐다. 문서 고침을 되돌리고 dev를 합친 뒤 다시 고쳤다.

## 한 일

티켓의 수락 기준 아홉 줄을 모두 채웠다.

- `tools/release.py`(새 파일): 표준 라이브러리만 쓴다. CI가 의존성을 깔지 않은 잡에서 `python3 tools/release.py`로 부르기 때문이다. 하위 명령은 `number`(릴리스할지와 다음 번호), `notes`(릴리스 노트), `bundle`(배포 파일 묶음)이고, 순수 함수로 `judge_number_tag`(번호 태그 판정)와 `classify` 등이 있다. git 호출마다 `GIT_TIMEOUT`(60초)을 둔다.
- 제품 변경의 경로 `PRODUCT_PATHS`는 `src`, `pyproject.toml`, `uv.lock`, `deploy` 넷이다. `README.md`, `docs/`(릴리스 노트 원고 포함), `compose.test.yml`, `compose.eval.yml`은 세지 않는다.
- 번호 규칙은 `deploy/release.toml`의 `candidate_for`가 가리키는 판의 출시 후보 `-rc.N`을 이어 가는 것이다. 첫 릴리스는 `0.1.0-rc.1`이다. 제목은 `tools/check_commit_msg.py`의 `PATTERN` 하나로 읽는다(agent-os와 같은 파일이다).
- 릴리스 노트의 절 차례는 경고, 소개, 기능 소개, 업그레이드할 때 할 일, 계약의 판, 새 기능, 고친 것, 그 밖의 변경이다. "계약의 판"은 agent-os에 없던 절이다. `--contract-versions PATH`로 받은 파일의 줄(`rag-engine --version`의 둘째 줄부터)을 ```text 울타리 안에 싣는다. 파일이 없거나 읽지 못하거나 비었거나 백틱 셋으로 시작하는 줄이 있으면 노트를 짓지 않고 종료 1로 끝난다.
- 배포 파일 묶음 `rag-engine-<번호>.tar.gz`: 틀의 자리 표지는 `@RAG_ENGINE_VERSION@`(릴리스 번호)과 `@RAG_ENGINE_NAMESPACE@`(이미지 이름공간) 둘이다. 그 밖의 `@RAG_ENGINE_…`이 남으면 묶음을 짓지 않는다. 풀면 `rag-engine-<번호>/` 하나가 나오고, 같은 입력이면 바이트가 같고, 빈 하위 폴더와 심볼릭 링크는 담지 않는다.
- `tests/tools/test_release.py`: agent-os 시험 사례를 모두 옮기고(함수 목록을 원본과 대 봤다) 새 사례를 더했다. 제품 변경 경로 셋의 사례, "계약의 판" 절의 시험, 자리 표지 시험, 스크립트로 불러 노트와 묶음이 나오는 시험이 새것이다. `Repo` 보조 클래스는 `tools.run_hooks.REPO_LOCATION_VARS`를 자식 환경에서 벗긴다.
- `docs/constitution/operations.md`: 제품 변경 경로 목록을 `tools/release.py`의 `PRODUCT_PATHS`를 가리키는 한 줄로 줄였다. 헌법 문서를 고쳤으므로 `docs/constitution/README.md`의 판을 올렸다. 사용자의 승인 질문은 1.5.0에서 1.5.1이었으나 그 사이 dev가 1.5.1을 가져가서 문구 수정(patch) 한 칸을 더 올려 1.5.2로 했다.
- 티켓 파일: 상태를 `done`으로, 체크박스를 모두 채우고 Comments에 구현 보고를 적었다.
- 이 티켓이 들이지 않은 것: `tools/check_notes.py`(05), `tools/release_ci.py`와 릴리스 워크플로(08)는 후속 티켓의 몫이다. 도구 독스트링이 그 이름을 미래형으로 부르는 자리는 그 티켓이 닫힐 때 걷는다.

## 확인한 것

- 이 파일만 돌린 시험은 109개가 통과했다(셀프 리뷰 반영 뒤, 반영 전에는 104개). 린트(`ruff check`)와 포맷(`ruff format`)은 두 파일 모두 통과했다.
- 시험은 도구보다 먼저 썼으나 처음 빨강만 따로 돌려 보지는 않았다. 모듈이 없어 수집 단계에서 실패하는 상태였다.
- 셀프 리뷰를 반영한 뒤 처음부터 돌린 `uv run python tools/run_checks.py`는 `test-db`, `check-ticket`, `zizmor`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright-linux`, `pyright`, `run-hooks`, `pytest`(472.3초)가 모두 통과했다. 저장소 전체의 `ruff check`와 `ruff format --check`도 통과했다. `tools/sibling_overlap.py`는 번호 겹침이 없고 함께 고친 파일이 없다고 했다(헌법 판은 형제의 가장 높은 값 1.5.1보다 높은 1.5.2).
- 그 뒤 PR 직전 리뷰를 반영해 도구 두 곳을 더 고쳤다(아래 "PR 직전 리뷰"). 그 변경은 이 파일만 돌린 시험 110개 통과로 확인했고, 전체 러너는 커밋이 부르는 pre-commit이 다시 돈다. 그 결과는 아래 "커밋"에 적는다.
- 아래 "셀프 리뷰"가 낸 사실 주장은 코드와 파일을 직접 읽어 확인했다.

## 셀프 리뷰

`/code-review`의 표준 축(sonnet / high)과 명세 축을 나란히 돌렸다. 범위는 base `75cb8ea`, 파일 다섯(추적 변경 셋, 추적하지 않는 새 파일 둘), 커밋 0이다. 지적마다 근거를 읽고 판정했다. 명세 축은 체크박스 아홉 가운데 표지 검사만 부분으로 보았고 나머지는 충족으로 보았다. 표준 축의 smell 목록(Primitive Obsession, Data Clumps, Repeated Switches, Divergent Change, Duplicated Code 등)은 원본 agent-os에서 온 모양이고 `CODING_STANDARDS.md`가 그 모양을 문제로 두지 않아 판단 항목으로 남기고 고치지 않았다.

- 고쳤다(둘 다 Major, 근거 문장): 시험 파일의 `EXISTING` 주석이 이 저장소에 없는 프로브 경로 `.scratch/release-image/probes/release_mechanics/README.md`를 가리키고, 이 저장소에서 조회한 출력인 것처럼 적었다. agent-os가 2026-11-16에 적어 둔 꼴을 옮기고 이름만 바꿨다는 말로 고쳤고, 이 저장소에서는 조회하지 않았다고 적었다. 그 워크플로가 08에서 들어온다는 말도 붙였다.
- 고쳤다(Minor): 자리 표지 검사 `_MARKER`가 `@RAG_ENGINE_[A-Za-z0-9_]+@`라서 `@RAG_ENGINE_TYPO`(닫는 `@` 없음), `@RAG_ENGINE_A-B@`, `@RAG_ENGINE_@`로 묶음이 지어졌다. 티켓과 독스트링은 "`@RAG_ENGINE_`으로 시작하는 다른 표지"이다. 검사를 `@RAG_ENGINE_[^@\s]*@?`로 넓히고 세 사례를 시험 하나(매개변수 셋)로 고정했다.
- 고쳤다(Minor): 독스트링의 "계약의 판" 서술이 동작과 달랐다. 실제로는 CRLF를 LF로 맞추고, 백틱 셋으로 시작하는 줄이 있을 때만 거절한다. 모듈 독스트링, `_contract_section`의 독스트링, `--contract-versions`의 도움말(필수라는 말)을 고쳤다.
- 고쳤다(Minor): 새로 적은 못 보는 것 항목 "첫 줄까지 담아 넘겨도 그대로 싣는다"를 고정한 시험이 없었다. CRLF 맞춤과 첫 줄 포함을 함께 보는 시험을 더했다. 같은 이유로 UTF-8이 아닌 파일의 갈래를 `test_노트_도구는_계약의_판_파일이_없거나_읽지_못하면_실패한다`에 더했다.
- 고쳤다(Minor): 실패 시험이 "계약의 판"만 대어 네 실패 갈래(옵션 없음, 읽기 실패, 빈 줄, 울타리)를 가르지 못했다. 갈래마다 다른 문구(`--contract-versions 가 없다`, `파일을 읽지 못했다`, `줄이 비었다`, `코드 울타리`)로 바꿨다.
- 고쳤다(Minor): `notes`와 `bundle`을 스크립트 경로(`python3 tools/release.py …`)로 밟는 시험이 없었다. CI가 부르는 꼴 그대로 두 하위 명령을 subprocess로 돌려 한국어 노트가 깨지지 않는지, 묶음 경로가 나오는지 보는 시험을 더했다. 윈도의 텍스트 stdout이 줄바꿈을 CRLF로 내서 시험이 맞춘 뒤 대도록 했다.
- 고쳤다(Nit): 모듈 독스트링의 "ci.yml 의 ticket 잡이 커밋 검사를 그렇게 부른다"가 부정확했다. `ci.yml`의 `ticket` 잡은 `python3 tools/check_ticket.py --ci`를 부른다. 그 문장으로 고쳤다.
- 고쳤다(Minor): `--full-history`의 근거를 "근거로 적은 것"이라 했으나 agent-os의 그 README 7번은 안전한 쪽이라는 것을 어림으로 적었다. "안전한 쪽이라고 어림해 적은 것"으로 고쳤다.
- 남긴다: `"feat"` 분기, `(repo, since, head)` 뭉치 같은 smell은 원본에서 온 모양이다. 파일을 쪼개는 일은 이 티켓의 체크박스가 아니다. 독스트링이 후속 티켓(05, 08)을 미래형으로 부르는 문장은 지금 PR에서는 맞고 그 티켓이 닫힐 때 걷는다.
- 남긴다: 계약 줄 처리의 BOM만 든 파일과 U+200B만 든 파일은 통과해 빈 `text` 블록이 선다. 공백이 아닌 문자가 있는 줄로 세는 것은 독스트링대로이고, 릴리스 워크플로가 `rag-engine --version`의 출력을 넘기므로 나올 길이 없다.
- 사용자가 알아야 할 것: "계약의 판" 절을 ```text 울타리에 싣고 앞뒤 빈 줄을 덜고 CRLF를 LF로 맞추며 울타리 줄이 있으면 실패시키는 것은 명세가 정하지 않은 구현 선택이다(명세는 "둘째 줄부터를 그대로 옮긴다"만 적는다). 시험이 고정했고 08이 이 꼴로 부른다.

고치며 새로 쓴 사실 문장(PR 직전 리뷰가 밀 주장):

1. 모듈 독스트링의 "ci.yml 의 ticket 잡이 `python3 tools/check_ticket.py --ci` 로 도는 것과 같은 길이다".
2. 시험 파일 `EXISTING` 주석의 "agent-os 저장소가 2026-11-16 에 … 적어 둔 꼴을 옮기고 이름만 이 저장소의 것으로 바꿨다(그 워크플로는 release-image 의 08 이 들인다). 이 저장소에서는 조회해 보지 않았다".
3. 모듈 독스트링의 "백틱 셋으로 시작하는 줄이 있으면 … 실패한다", "줄바꿈 꼴(CRLF 등)만 LF 로 맞춘 줄".
4. `_MARKER`가 닫는 `@`가 없는 `@RAG_ENGINE_TYPO`와 `@RAG_ENGINE_A-B@`, `@RAG_ENGINE_@`를 모두 잡는다는 것.
5. `--full-history`의 근거를 "안전한 쪽이라고 어림해 적은 것"이라 한 것.

다시 돌린 명령: `uv run pytest tests/tools/test_release.py` 109개 통과, `uv run ruff check`와 `uv run ruff format` 통과. 전체 러너는 아래 "커밋"에서 돌린다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트가 CodeRabbit CLI 0.7.5를 끝까지 돌렸다(`--base 75cb8ea76f917251e5c2c57272d4f4511e41c0a8`, 스테이지된 변경 전부). 좌석은 `Seat: not assigned`, 플랜은 Free였지만 리뷰는 끝났다. 결과는 9건이고 Critical과 Major가 없으며, 유효한 Minor 셋과 Nit 셋, 오탐·보류 둘(서브에이전트 보고가 세는 기준으로 유효 5, 오탐·보류 4)이다. 비밀 값이나 질문 내용을 남기게 하는 문장은 없었다. 밀어 달라고 넘긴 새 사실 문장 일곱은 대체로 맞았다. 서브에이전트가 스크래치 스크립트로 `_contract_section`과 `_contract_text`를 경계 입력으로 직접 불러 재 보았고, `ci.yml` 143행과 agent-os 프로브 README의 해당 문장은 직접 열어 확인했다. 시험 수 109와 판 1.5.2도 맞았다.

- 고쳤다(Minor): `_warning_lines`가 Grype 결과의 `matches` 키가 있는지만 보고 형은 보지 않았다. `"matches": null`이나 목록이 아닌 값이면 빈 목록으로 읽어 경고가 조용히 빠진다. 목록이 아니면 "거르지 않은 JSON 이 아니다"로 실패시키고, 두 사례를 기존 시험에 더했다.
- 고쳤다(Minor): `_collect`가 틀 폴더 자체가 심볼릭 링크인지 보지 않아 링크 대상을 따라가 틀 밖의 파일을 담을 수 있었다. 하위 링크만 막고 있었다. 틀 폴더가 링크이면 실패시키고 시험을 더했다(윈도에서 링크를 만들 권한이 없을 수 있어 하위 링크 시험처럼 `is_symlink`만 바꿔 같은 길을 밟는다).
- 남긴다(Minor): 업그레이드 원고를 더한 뒤 이름을 바꾸면 머리의 옛 경로 조회가 비어 더한 커밋 시점의 옛 글을 싣는다. 같은 모양이 agent-os 원본에 있고, 이 티켓의 체크박스는 원본 기능의 이식이다. 이름 바꾸기를 따라가는 일은 이 도구를 쓰는 릴리스에서 실제로 나는지 본 뒤에 정한다.
- 남긴다(Nit): `_moved_in`이 지난 릴리스와 머리의 끝점만 견줘서, 범위 안에서 `alpha`를 `beta`로 옮기고 새 `alpha`를 더하는 드문 경우를 놓친다(독스트링이 말한 한계와 겹친다). 출력 폴더가 틀 폴더 안일 때 둘째 실행이 첫 묶음을 다시 담는 것도 기본 호출(`--out .`, 틀 `deploy/standalone`)에서는 나지 않는다. `Digest:` 줄의 값 꼴을 검사하지 않는 것은 깨진 값이면 거부로 가는 안전한 쪽이다.
- 남긴다(Nit): `splitlines()`가 U+000B, U+000C, U+0085, U+2028도 줄바꿈으로 가른다. 독스트링의 "CRLF 등"에 든다. `foo@RAG_ENGINE_x` 같은 글도 자리 표지로 읽혀 막히는 것은 막는 쪽이 안전하고 메시지가 분명해서 둔다.
- 오탐·보류: `judge_number_tag`의 HOLD가 08의 실제 buildx 출력과 다를 수 있다는 지적은 추측이고 HOLD는 안전한 쪽이라 08로 넘긴다(이 저장소에서 조회하지 않았다는 점은 두 파일의 주석에 이미 적었다). `_added`와 `_upgrade_entry`가 git의 `-z` 출력을 쓰지 않는 것은 `core.quotepath=false`가 이미 있고 원고 경로에 탭이나 줄바꿈이 올 일이 없어서 둔다.

이 절에서 새로 쓴 사실 문장은 모두 서브에이전트의 보고와 내가 열어 본 파일에서 옮긴 것이다.

## 회고

`retro` 스킬을 돌렸다. 후보는 여섯이고 승인 하나, 넘김 없음, 기각 다섯이다.

1. **승인(회차로 센다).** 시험 파일의 `EXISTING` 주석이 이 저장소에 없는 프로브 경로(`.scratch/release-image/probes/release_mechanics/README.md`)를 근거로 들고, agent-os가 적어 둔 출력을 이 저장소에서 조회한 것처럼 적었다. 티켓 Comments는 같은 종류의 문장을 "시험 머리 주석도 고쳤다"고 적었지만 이 블록은 남아 셀프 리뷰 두 축이 모두 잡았다. 옮기는 변경이 원본의 출처 문장을 그대로 가져오고, 고친 뒤 옛 표현(`release_mechanics`)을 grep해 잔존 0을 보라는 `CLAUDE.md` 작업 규약 4의 확인이 모자랐다. 대기열 `measured-claim-beyond-probe`의 15회차로 더했다. 이 항목은 이미 5회차를 넘어 chore 계기라 이번에는 새 처방을 따로 더하지 않았다.
2. **기각.** 윈도에서 `notes`를 subprocess로 돌린 시험이 줄바꿈 CRLF 때문에 처음에 실패했다. 시험이 그 자리에서 잡았고 맞춘 뒤 대도록 고쳤다.
3. **기각.** `ruff`의 줄 길이(E501)를 넘긴 독스트링 한 줄을 훅이 알렸다. 이미 있는 훅이 그 자리에서 알렸다.
4. **기각.** 작업 중 `origin/dev`가 헌법 판 1.5.1을 가져가서 판을 1.5.2로 올려야 했다. `sibling_overlap.py`가 겹침을 알렸고 잃은 것이 없다.
5. **기각.** 합친 한 줄 명령을 워크트리 가드가 거부했고, 영문 중간 문장과 파이프로 이은 게이트 명령을 훅이 알렸다. 이미 있는 가드와 훅이 그 자리에서 막거나 알렸다.
6. **기각.** 승인 질문에 쓴 판 번호(1.5.1)가 병합 직전에 달라졌다. 일지에 까닭을 적었고 승인한 문장은 그대로여서 잃은 것이 없다.

만료는 `uv run python tools/queue_open_rows.py`의 "만료할 항목"이 (없음)이라 닫을 것이 없었다. 문턱을 지난 새 훅·검사가 없어 `tools/hook_report.py`는 돌리지 않았다.

## 다음

이 PR(base dev)은 헌법 판 1.5.2(문구 수정)를 올린다. 병합 뒤 release-image의 프런티어에서 02가 빠지므로 03(단독 compose)과 05(노트 검사)가 열린다. 03은 01과 02를 기다렸고 이제 둘 다 있다. 05는 02의 `PRODUCT_PATHS`와 제목 읽기를 가져다 쓴다. 04는 03 뒤, 08은 01부터 07까지가 모두 닫힌 뒤다. 08이 `rag-engine --version`의 둘째 줄부터를 `--contract-versions` 파일로 만들어 `tools/release.py notes`에 넘기는 호출 꼴은 도구 독스트링과 티켓 Comments에 적어 두었다. 세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
