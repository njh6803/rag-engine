# core 08 파서와 격리 일지 · 2026-11-11

티켓 `.scratch/core/issues/08-parsers-isolation.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/08-parsers-isolation`, 작업은 워크트리 `parsers-isolation`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 07 일지의 "코드 리뷰"와 "다음", 09 티켓.
- 지시문대로 `tidy-checkouts`를 먼저 돌고 워크트리에 들어가 브랜치를 땄다.
- 의존성을 둘 더했다(`pdfplumber`, `python-hwpx`). `docs/constitution/tech.md`의 스택 표와 맞는지 확인했고, 둘 다 파서 entry point(`pdf`, `hwpx`)로 등록한다. 설치된 판(pdfplumber 0.11.10, pdfminer.six 20260107, python-hwpx 6.11.0)은 명세가 근거로 든 프로브(`.scratch/core/probes/parsers/limits_probe.py`의 README 줄)가 잰 판과 같아 측정을 다시 돌리지 않았다.
- 테스트 PostgreSQL은 `docker compose -f compose.test.yml up -d --wait`로 올렸고 명령마다 `RAG_TEST_DATABASE_URL`을 내보냈다. 세션이 끊긴 사이 Docker Desktop이 꺼져 있어 다시 켰다.

## 정한 것

- **PDF 파서**(`adapters/parsers/pdf_parser.py`): 쪽마다 글줄을 읽어 앞 줄과의 세로 간격이 앞 줄 높이의 0.75배를 넘는 곳에서 문단을 가르고, 표 추출로 나온 영역은 표 블록 하나로 낸다. 표는 행마다 한 줄, 칸은 ` | `로 잇고 공백을 접는다. 쪽 번호는 1부터다. 암호 PDF는 `encrypted_document`, 쪽 수 초과는 `too_many_pages`다. pdfplumber가 pdfminer의 예외를 `PdfminerException`으로 감싸서 원인을 풀어 갈랐고, 쪽 수는 본문을 읽기 전에 `PDFPage.create_pages`를 `islice`로 세어 상한을 넘으면 읽지 않는다.
- **HWPX 파서**(`adapters/parsers/hwpx_parser.py`): python-hwpx로 문단과 표를 읽고, 문단 모양의 개요 수준이 있으면 제목 블록(수준은 개요 수준 + 1, `Block`의 제목 수준은 1부터)으로 낸다. 글이 없는 문서는 블록 0개로 성공한다.
- **ZIP 사전 검사**(`adapters/parsers/zip_guard.py`): 부모가 압축을 풀지 않고 목록만 읽는다. 항목이 4096개를 넘는 것, 압축 해제 크기 합계가 `RAG_PARSE_MAX_UNZIPPED_MB`를 넘는 것, 압축된 크기가 1MiB를 넘는 항목의 압축비가 `RAG_PARSE_MAX_COMPRESSION_RATIO`를 넘는 것은 `compressed_too_large`로, 암호 항목은 `encrypted_document`로 거른다. 목록을 읽을 수 없으면 `parse_failed`다. 중앙 디렉터리가 파일 안에 들어가는지는 `domain/media_types.central_directory_fits`(공개로 바꿨다)가 먼저 본다. 이 검사는 DOCX와 HWPX 둘 다 지난다.
- **실행기의 한도**(`adapters/parsers/runner.py`): 자식의 메시지는 JSON 바이트이고 부모는 `recv_bytes(maxlength=)`로 받는다. 상한은 글 크기 상한의 여섯 배에 1MiB다(JSON이 제어 문자 하나를 여섯 바이트로 쓰는 것이 최악이다). 넘으면 `document_too_large`다. 기한은 감시 타이머가 수신 전체에 건다. 자식이 메모리 한도로 죽거나 `MemoryError`를 내면 `parse_memory_exceeded`다(리눅스는 `RLIMIT_AS`로 건다. 윈도는 걸지 않고 첫 파싱에서 `parse_memory_limit_not_applied`를 한 번 남긴다). 뽑은 글에서 U+0000을 지우고 글 크기를 UTF-8 바이트로 센다.
- **파싱의 영구 실패 종결**(`app/index_document.py`의 `_record_permanent_failure`): 파싱이 `PermanentFailure`를 올리면 같은 작업 단위에서 세대와 작업 행 조건을 대조한 뒤 문서를 `failed`와 오류 코드로 쓰고, 살아 있는 판마다 옛 조각을 지우고 색인 상태를 `failed`로 쓴다. 건설 중인 판이면 전환 검사(`_check_version_switch`, 14가 채울 자리)를 부른다. 세대가 다르면 문서도 색인도 건드리지 않는다. 어느 쪽이든 실패를 그대로 올려 작업이 재시도 없이 `failed`로 끝난다. 파싱을 건너뛰는 재수집에서 문서 상태가 `failed`나 `received`로 남아 있으면 `parsed`로 되돌린다(바꿨다가 되돌린 문서가 그 경우다).
- **entry point의 major 거부**는 새로 만들지 않았다. PDF·HWPX가 DOCX와 같은 길(`discover_parser_specs`)로 등록되어 07의 거부를 그대로 받는다는 것만 시험이 본다.
- **픽스처**: 글이 든 작은 PDF 하나(`tests/fixtures/small_text.pdf`)만 저장소에 두고(`.gitattributes`에 binary 줄을 더했다), 암호 PDF·압축 폭탄·쪽 많은 PDF·HWPX는 시험이 만든다(`tests/support/{pdf,hwpx,zip}_files.py`).

## 손으로 본 것

- **윈도에서 기한 시험이 영원히 막혔다.** 변이 6번(감시 타이머를 켜지 않는다)의 기준선이 300초를 넘겨서 알았다. 진단 스크립트(커밋하지 않았다)로 가렸다. 감시 타이머가 자식을 `kill()`로 죽였는데(종료 코드 -15) 부모의 `recv_bytes`가 풀리지 않았다. 원인은 윈도의 `multiprocessing`이 자식에게 줄 연결 핸들을 부모 안에 복제해 두었다가 자식이 기동한 뒤에 가져가며 원본을 닫는 방식이라, 자식이 기동하기 전에 죽으면 부모에 복제본이 남아 쓰기 쪽이 닫히지 않는 것이다. 리눅스는 fd 상속이라 해당 없다. 수신을 `wait([receiver, process.sentinel])`로 바꿔 자식이 메시지 없이 끝나면 바로 깨어나게 했다. 회귀 시험은 기한을 0초로 줘 타이머가 기동 전에 자식을 죽이게 한다. 수정 전 코드에서 이 시험이 30초 기한을 넘겨 `TimeoutError`로 빨강인 것을 손으로 확인했다(프로브가 아니다. 변이 표에는 넣지 않았다. 기다림을 지우는 변이는 수신이 영영 막혀 pytest가 스레드를 붙잡고 끝나지 못하므로 변이 도구가 끝낼 수 없다).
- **플랫폼마다 달라지는 갈래.** 리눅스의 `Pipe`는 길이를 앞에 단 틀이라 일부만 쓰고 멈추면 `recv_bytes`가 막히고 윈도는 한 번의 쓰기가 온전한 메시지라 일부만 쓸 수 없다. 그래서 "절반만 보내고 멈추는 파서" 시험의 윈도 갈래는 잘린 JSON이 `parse_failed`로 가는 것과 수신이 막히지 않는 것만 본다. 수신 중 기한은 리눅스 갈래가 본다(CI가 처음 돈다). `recv_bytes(maxlength)`를 넘으면 두 플랫폼 모두 `OSError("bad message length")`를 낸다. 이 문구는 CPython 내부 문구라 바뀌면 `document_too_large`가 조용히 `parse_failed`가 된다. 두 플랫폼의 시험이 문구를 고정한다.
- 시험 표지 고르기에서 돌아갔다. 변이 표의 `expect_output`이 시험 원문에 든 글자라며 거절되어(표지의 메아리) 두 표지를 `<ErrorCode.PARSE_FAILED: 'parse_failed'>` 꼴과 pytest가 찍은 줄(`Left contains one more item: …`, `Failed: DID NOT RAISE PermanentFailure`)로 바꿨다.
- **변이.** 시험 일부를 구현 뒤에 쓰거나 처음부터 초록이라 `tools/mutate.py`의 표(`.scratch/core/probes/parsers_isolation_mutations.toml`)로 일곱을 돌렸다. 영구 실패가 세대를 대조하지 않는다, 옛 조각을 지우지 않는다, 전환 검사를 부르지 않는다, 문서에 오류 코드를 쓰지 않는다, 건너뛴 문서를 `parsed`로 되돌리지 않는다, 감시 타이머를 켜지 않는다, ZIP 사전 검사를 부르지 않는다가 그것이고 모두 기대한 표지와 함께 빨강이다.
- **07의 변이 표 둘이 이 변경에 깨졌다.** 첫 커밋 시도에서 pre-commit의 `check-mutations`가 알렸다. 시간 초과 변이(`first_round_trip_adapter_mutations.toml` 11번)의 원문이 옛 `receiver.poll(...)` 줄이었는데 수신을 다시 써서 0번이 되었고, 세대 대조 변이(`first_round_trip_mutations.toml` 1번)의 원문은 영구 실패 종결이 같은 두 줄을 되풀이해 2번이 되었다. 시간 초과 변이는 새 코드의 원문(감시 타이머 시작 줄)과 그 시험 하나로 옮기고, 세대 대조 변이는 뒤의 줄을 붙여 한 번만 맞게 했다. 둘 다 다시 돌려 기대한 표지로 빨강임을 보았다.
- 한 번 틀린 것: 시험을 고치다 앞 시험의 마지막 단언이 다음 시험 끝에 붙은 것을 되돌렸다. `pyright: ignore`로 `_registry`를 읽던 시험 코드는 원칙 II 위반이라 `ParserRegistry(discover_parser_specs())`를 직접 만들게 바꿨다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `1ab024d`, 수정한 파일 13개, 추적하지 않는 새 파일 11개(디렉터리 포함), 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았고, 근거는 내가 코드에서 다시 열어 확인했다. Critical은 없었다.

**고친 것**

- 두 축이 함께 낸 Major급 사실 오류: 받는 크기 상한이 "글 크기의 두 배"인데 JSON은 제어 문자(U+0000 포함)를 여섯 바이트로 쓴다. 글이 한도 안이어도 메시지가 상한을 넘어 `document_too_large`가 난다. 상한을 여섯 배로 올리고 주석을 고쳤다. 새 시험(`test_제어_문자로_부푼_메시지도_글이_한도_안이면_받는다`)은 옛 상수(2)에서 `document_too_large`로 빨강이었다.
- 명세 축: 실제 `RLIMIT_AS`를 거는 시험이 없었다. 768MiB를 잡는 `AllocatingParser`를 더했고 리눅스는 `parse_memory_exceeded`, 윈도는 한도가 걸리지 않아 성공이라는 두 갈래를 시험했다.
- 명세 축: 글이 없는 문서가 작업자를 거쳐 문서 `parsed`와 조각 0개로 끝나는 시험이 없었다. 더했다(`test_글이_없는_HWPX는_조각_없이_parsed로_끝난다`).
- 미래형 문장: `worker/processing.py` 독스트링의 옛 문장(끝냄과 재시도를 08과 12가 채운다는 것)과 `tests/app/test_process_job.py` 독스트링이 08이 한 일을 하지 않은 것으로 적었다. 고쳤다.
- 독스트링 모순: `index_document.py`의 "세대가 다르면 성공으로 끝낸다"에 파싱의 영구 실패는 예외라는 문장을 더했다.
- 시험 이름: `test_메시지를_보내다_멈춘_자식도_시간_제한이_덮는다`는 윈도 갈래가 이름의 행동을 재지 않아 `…수신이_영영_막히지_않는다`로 바꿨다.
- 근거 문장: 변이 표 주석의 "수정 전 코드에서 직접 봤다"를 프로브가 아니라 손으로 본 것이라고 고쳐 이 일지에 가리킨다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `adapters/parsers/runner.py`의 상수 주석: JSON은 따옴표와 역슬래시, 줄바꿈을 두 바이트로, 그 밖의 제어 문자(U+0000 포함)를 여섯 바이트(`\u0001`)로 이스케이프하고, 그래서 메시지는 글의 최대 여섯 배까지 커진다.
- `adapters/parsers/runner.py`의 수신 주석: "윈도는 자식에게 넘길 연결 핸들을 부모 안에 복제해 두었다가 자식이 기동한 뒤에 가져가므로, 그 전에 죽은 자식의 파이프는 끊기지 않는다."
- `tests/support/fake_parsers.py`: "`RLIMIT_AS`가 걸린 자식에서는 한도를 넘어 `MemoryError`가 나고, 한도를 걸지 않는 윈도에서는 그대로 성공한다."
- `worker/processing.py`: "파싱의 영구 실패는 08이 문서와 색인에 적고 이 모듈이 작업을 재시도 없이 `failed`와 그 코드로 끝낸다."

**남긴 것과 이유**

- 판단 항목이라 손대지 않았다. 회고가 다섯 번째 반복인지 센다.
  - Duplicated Code: 표를 "행마다 한 줄, 칸은 ` | `"로 만드는 로직이 `pdf_parser`와 `hwpx_parser`에 따로 있다. `check_zip_container`와 `media_types._sniff_zip`가 같은 `except (BadZipFile, …)`를 되풀이한다. `_record_permanent_failure`가 셋째 단계의 쓰기 단위와 모양이 같다(14가 `_check_version_switch`를 채울 때 합칠 후보).
  - 추상화 수준: `_run_child`가 기동, 감시 타이머, 수신, 회수를 한 함수에서 한다. 수신부를 따로 빼는 것이 후보다.
  - Primitive Obsession(Nit): `pdf_parser`의 `_Item` 튜플과 같이 다니는 `previous_top`·`previous_bottom`.
  - Nit: `central_directory_fits`가 거짓이면 ZIP64도 같은 "목록이 한도를 넘었다" 메시지다. `pdf_parser`가 pdfminer를 직접 import하지만 선언한 의존은 pdfplumber뿐이다(전이 의존이라 `tech.md`와 ADR 없이 더하지 않았다).
- 시험이 구현에 묶인 곳: `test_영구_실패는_살아_있는_판_모두에…`가 비공개 `_check_version_switch`를 monkeypatch한다. 14가 그 자리를 채우면 공개 행동으로 바꾼다.
- 티켓과 다르게 한 것: 없다. 요구 밖인 `wait([receiver, process.sentinel])`는 "시간 제한이 수신 전체를 덮도록"을 윈도에서 성립시키는 데 필요해서 더했다.

**다시 돌린 명령**

- 새 시험 셋 가운데 제어 문자 시험은 옛 상수(2)에서 `document_too_large`로 빨강이었고 구현 뒤 초록이다. 리눅스 컨테이너(`python:3.12.10-slim-bookworm`, `uv sync --frozen`)에서 실행기·ZIP·PDF·HWPX 시험 57개가 통과했다(`RLIMIT_AS` 갈래와 수신 중 기한 갈래 포함). 컨테이너가 앞서 상한을 올린 뒤의 "상한을 넘는 메시지" 시험(4MiB)이 더는 넘지 못하는 것을 잡았고 8MiB로 고쳤다.
- 반영을 마친 트리에서 `ruff check .`, `ruff format --check .`가 통과이고, `uv run python tools/run_checks.py`가 `test-db`, `check-ticket`, `zizmor`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest` 모두 통과다(pytest 247초). 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌린다(결과는 커밋 뒤에 적는다).

### PR 직전 리뷰(CodeRabbit CLI가 돌지 못해 대체 둘)

`coderabbit-review` 에이전트가 `coderabbit review --agent --include-untracked --base main`을 쳤으나 Claude Code의 자동 모드 분류기가 코드 diff를 외부 서비스로 보내는 명령이라며(`Data Exfiltration`) 거절했다. 시도는 한 번이고 우회하지 않았다. CLI는 설치(0.7.5)되어 있고 로그인되어 있으며 `Seat: not assigned`, `Plan: Free`였다. PR 템플릿이 정한 대체 둘을 돌렸다. `origin/main`을 합친 뒤(병합 커밋 `087d4fd`)에 돌았다.

- 보안(`/security-review`, 식별 하위 작업 하나): 발견 없음이라 오탐 거르기 하위 작업은 띄우지 않았다. 확인한 길은 pickle 없는 수신(`send_bytes`와 `recv_bytes(maxlength)`, 스키마 검증), entry point의 임포트 대상, ZIP 목록 검사, python-hwpx 6.11.0(메모리에서만 읽고 `resolve_entities=False, no_network=True`, 항목 이름 검사)과 pdfminer.six 20260107(cmap을 pickle이 아니라 `json.gz`로 읽고 경로를 디렉터리 안으로 제한), 오류·로그에 문서 내용이 실리는지(고정 문구와 오류 코드만), 의존성 출처다. 참고로 자식이 부모의 환경 변수를 그대로 물려받는다(아래 열린 일).
- 버그·성능(`bug-perf-review`): Critical·Major 없음, 지적 넷(Minor 둘, Nit 둘). 경쟁 경로(`wait` 뒤 `poll`이 거짓이 되는 길을 윈도에서 크기 10B·200KB·20MB로 반복해 실패 0회, `timed_out` 표지의 순서, ZIP 위조 크기, 영구 실패 종결의 임대 상실)는 따라가 닫았다.

**고친 것**

- HWPX 파서가 비어 있지 않은 문단마다 `styles.paragraph_property`를 불러 라이브러리가 매번 헤더의 모든 문단 모양을 훑는다. 문단 2만 개 문서가 6.85초 걸렸고(5천 개를 프로파일하니 3.8초 가운데 3.6초가 `_outline_level`) 선형으로 늘어난다. 문단 모양(`para_pr_id_ref`)마다 한 번만 찾게 했다. 새 시험(`test_같은_문단_모양을_쓰는_문단은_개요_수준을_한_번만_찾는다`)은 옛 코드에서 `[31, False]`로 빨강이었다.

**PR 직전 리뷰에 밀 주장**

- `adapters/parsers/hwpx_parser.py`의 주석: 라이브러리의 문단 모양 조회는 부를 때마다 헤더의 모든 문단 모양을 훑으므로 모양마다 한 번만 찾는다.

**남긴 것과 이유**

- Minor: 받는 메시지 상한(글 상한 × 6 + 1MiB, 기본 설정에서 약 385MiB)이 크고, 글 크기는 디코드 뒤에 본다. 최대치는 payload의 두 배(리눅스는 받는 동안 한 번 더 복사할 수 있다고 코드를 읽어 추정했고 재지 못했다)에 글이 더해진 값이다. 정상 문서(글 64MiB)는 문제없다. 설계의 수용 가능한 한계라 작업자의 메모리 예산을 13이 동시 처리를 넣을 때 정한다(열린 일).
- Nit: 파싱이 영구 실패한 작업의 `job_finished`가 `parse_ms=0`을 남긴다(`process_job`이 `RagEngineError`에서 `_NO_TIMINGS`를 돌려준다). 12가 `_run`의 `except` 순서를 만질 때 고치도록 12 티켓에 적었다.
- Nit: `Pipe()` 뒤 `process.start()`가 예외를 내면 연결 둘이 닫히지 않고 GC가 거둔다. 자원 관리 문제이고 영구 누수가 아니라 보류했다.

## 회고

후보 열, 승인 둘(새 항목 하나와 기존 항목의 회차 더하기 하나), 기각 여덟, 넘김 없음이다. 이 세션에서 반영한 것은 없다. 만료할 항목은 `tools/queue_open_rows.py`가 없다고 냈다.

**승인**

- 스크립트가 쓴 저장소 파일의 CRLF. 사건: 작업 트리의 `tests/adapters/test_zip_guard.py`가 CRLF였고 `git add`의 `CRLF will be replaced by LF` 경고로야 알았다(`git ls-files --eol`이 `i/lf w/crlf`를 냈다). 어느 도구가 썼는지는 가리지 못했다(07 회고가 같은 근거로 센 꼴이다). `sed`로 LF로 되돌려 다시 스테이징했다. 층: 검사가 가장 높고 열린 항목 `crlf-from-script-edits`가 이미 그 처방을 든다. 되돌림: PR 하나. `crlf-from-script-edits`에 회차를 더했다. 병합하려 `origin/main`을 합치니 09 세션이 같은 항목에 3회차를 이미 더해 두어(충돌) 이 사건은 4회차가 되었다(더하는 것이라 다섯 번째에 반영한다).
- 윈도 PC에서 리눅스 갈래를 확인하는 컨테이너 실행. 사건: 리눅스에서만 서는 시험 갈래(`RLIMIT_AS`, 수신 중 기한)를 재려고 컨테이너 명령을 두 번 직접 지었고, 한 번은 `--exclude=.git`이 든 명령을 워크트리 가드가 거절했다. 컨테이너 실행이 상한을 올린 뒤 깨진 시험 하나를 윈도 부분 실행보다 먼저 잡았다. 층: 새 도구(`tools/linux_check.py`)가 지침보다 높다. 되돌림: PR 하나. 대기열 `linux-container-test-run`을 1회차로 더했다(더하는 것이라 다섯 번째에 반영한다).

**기각**

- 막힌 시험의 빨강이 오래 걸리고 pytest가 결과를 찍은 뒤에도 프로세스로 남은 일: 수신이 막힘을 재는 시험은 막힌 상태가 빨강이라 그때만 느리다(구현이 초록이면 2초). 막힌 스레드가 인터프리터 종료를 붙잡아 생긴 일이다. 변이 도구는 시간 제한에서 프로세스 트리를 이미 끝내고(`_kill_tree`), 그 변이는 표에서 빼 이유를 표에 적었다.
- 상수를 올린 뒤 그 상수에 기대던 시험(4MiB 메시지)이 컨테이너 실행에서야 빨개진 일: 전체 실행이 잡도록 둔 흐름이 제 몫을 했다.
- 코드 리뷰가 낸 거짓 주장(두 배 상한), 08을 아직 안 했다고 적은 미래형 문장, 독스트링 모순: `code-review`의 주장 검증 목록이 잡도록 둔 기준이라 리뷰가 제 몫을 한 것이다.
- 일지 초안에 기억으로 쓴 사실 둘(ZIP 오류 코드 이름, PDF 문단 간격 설명)을 코드와 대 보고 고친 일: 스스로 대조해 고쳤고 같은 실수가 반복된 적이 없다.
- 줄 길이(E501)를 넘긴 줄: 편집 훅이 그 자리에서 알렸다.
- 컨테이너 명령의 `--exclude=.git`을 워크트리 가드가 거절한 일: 가드가 그 자리에서 막았다(07 회고가 같은 가드의 거절을 같은 이유로 기각했다).
- PR 직전 CodeRabbit CLI 호출을 앱의 분류기가 외부 전송으로 거절한 일: 앱 가드가 그 자리에서 막았고, PR 템플릿이 이미 CLI가 못 돌 때의 대체(`/security-review`, `bug-perf-review`)를 정해 두어 그 길로 갔다. 분류기를 풀지는 사용자 판단이라 이 세션이 건드리지 않았다.
- 윈도 `multiprocessing`의 핸들 복제 사실: 사건 없이 떠올린 지식이다. 근거와 해법은 `runner.py`의 주석과 이 일지에 있다.

## 다음

- core의 프론티어는 09(검색의 완성)와 10(수집 갱신과 그룹 변경·재큐)이다. 둘 다 08이 병합되면 열린다.
- 08이 각 티켓에 넘긴 것: 14의 전환 검사는 `_check_version_switch`가 파싱의 영구 실패에서도 건설 중인 판에 불린다는 것을 알고 채운다(티켓 14가 "07·08·10·11·12가 둔 자리"라고 이미 적고 있다). `_record_permanent_failure`와 셋째 단계의 쓰기 단위가 같은 모양이라 14가 합칠 후보다.
- 열린 일:
  - 원본 바이트를 spawn 인자로 피클 복사하는 비용을 재지 않았다(07 일지가 08에 넘긴 것이다. 티켓 체크박스에 없어 재지 않았다. 100MB 원본에서 자식 기동 지연이 얼마인지 13이 동시 처리를 넣을 때 잰다).
  - 작업자의 메모리 예산: 받는 메시지의 최대치가 기본 설정에서 약 385MiB(payload의 두 배와 글이 겹쳐 더 늘 수 있다)이므로 동시 처리를 넣을 때(13) 작업자 한 개의 최대 메모리를 정한다.
  - 파서 자식이 부모의 환경 변수(데이터베이스 연결 문자열 등)를 그대로 물려받는다. 파서 라이브러리가 침해되면 자식이 읽을 수 있고 부모로 코드가 넘어오는 길은 막혀 있다. 강화에 해당해 이 PR에서 하지 않았다. 자식에 최소한의 환경만 넘기는 일(원칙 V)은 사용자가 정할 것이다.
  - 암호가 걸린 HWPX의 실제 구조를 확인하지 못했다. ZIP 사전 검사의 암호 항목 표지만 다룬다(그 표지가 서는 HWPX 파일을 구하지 못했다).
  - 윈도에서는 자식의 메모리 한도가 없고(`RLIMIT_AS` 갈래는 리눅스 시험이 본다), "절반만 보내고 멈추는 파서"의 수신 중 기한 갈래도 리눅스 시험만 본다. CI의 리눅스 실행이 처음으로 두 갈래를 돈다(이 PC에서는 컨테이너로 확인했다).
  - 자식 메시지의 오류 문구(`bad message length`)는 CPython 내부 문구라 판이 바뀌면 시험이 알려 준다.
  - 05에서 넘어온 것(확장자와 내용 불일치 판정, 키 길이 상한, `.env.example`, `request_failed` 이벤트, 토큰 목록의 회수 칸)은 여전히 사용자가 정할 것이다.
