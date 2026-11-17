# parse-runner-stall-test-deadline: 멈춘 자식 시험이 윈도에서 자식 기동 시간과 경쟁하지 않게 한다

**What to build:** `tests/adapters/test_parse_runner.py`의 `test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다`가 러너에 주는 기한(`timeout_seconds=2`)을 플랫폼별로 나눈다. 윈도는 30초, 리눅스는 지금처럼 2초다. 소요 상한은 고른 기한에 "여유"(15초)를 더한 값으로 둔다. 제품 코드와 `StallingMidMessageParser`는 손대지 않는다.

**승인:** 원칙 I(테스트가 실패하면 고치지 않고 멈춰 보고한다)에 따라 진단 세션이 원인과 갈래 셋(A 시험의 기한을 플랫폼별로, B 러너의 기한을 자식 기동 뒤부터 세게, C 그대로 재시도)을 보고했고, 사용자가 2026-11-13 대화에서 "A로 수정"이라고 답했다.

**왜 시험이 틀렸나.** 근거를 셋으로 가른다.
- 코드를 읽은 것: 러너의 감시 타이머는 `process.start()` 뒤에 시작하므로(`src/rag_engine/adapters/parsers/runner.py`의 `_run_child`) 자식의 interpreter 기동과 `runner`·`fake_parsers` import도 기한 안에 든다. 윈도의 기대(`parse_failed`)는 자식이 기한 안에 잘린 JSON을 보내야 선다. 기동이 기한을 넘으면 타이머가 자식을 먼저 죽여 `parse_timeout`이 난다. 리눅스의 기대(`parse_timeout`)는 어느 쪽이든 같아서 이 경쟁이 없다.
- 손으로 돌린 것(2026-11-13, 이 PC, Windows 10, Python 3.12.10): 시험만 홀로 돌리면 이 PC가 한가할 때 3번 모두 통과했다(약 2.5초). 같은 시험(`uv run pytest tests/adapters/test_parse_runner.py -q -p no:xdist -p no:cacheprovider -k 멈춘_자식이_있어도`)을 동시에 4개 돌리면 모두 통과했고, 8개는 3개, 16개는 11개가 `parse_timeout`을 받아 실패했다. 수정한 뒤에는 16개 두 번과 32개 한 번이 모두 통과했다.
- 프로브(커밋한 것): `.scratch/harness/probes/parse_runner_stall_deadline/stall_boot_race.py`와 출력 `stall_boot_race_out.txt`. 실제 러너와 `StallingMidMessageParser`로 기한만 바꿔 동시 16개를 돌리면 기한 2초는 `parse_timeout` 9개와 `parse_failed` 7개, 기한 10초는 16개 모두 `parse_failed`다. 32개는 기한 2초가 29개와 3개, 기한 10초가 32개와 0개다. 홀로 돌리면 자식이 보내기까지 0.7초 안팎이다.

일지에는 이 시험이 pre-commit의 전체 러너에서 빨갰고 그 파일만 다시 돌리면 통과했다는 기록이 적어도 다섯 있다(시험 이름을 적은 일지 기준: 2026-11-11-1941-core-11, 2026-11-12-1419·1914·2108, 2026-11-13-0124). 부하(다른 세션의 pytest, docker)가 걸린 때와 겹쳤다는 점도 같다. 이 시험이 들어온 뒤(`68aa7e0`) 시험, 러너, `StallingMidMessageParser`는 바뀐 적이 없어 빨간 커밋이 따로 없다.

**남긴 것(이 티켓의 범위 밖).** 윈도에서는 길이만 알리고 멈춘 자식을 만들 수 없어 이 시험이 실제로는 잘린 JSON의 분류(`parse_failed`)만 잰다. `parse_failed`는 자식이 import 중에 죽어 메시지를 못 낸 경우와 같은 코드이므로, 윈도 단언이 "잘린 메시지를 받았다"를 증명하지는 않는다. 리눅스는 자식이 한 글자도 못 보내고 죽어도 `parse_timeout`이라 이 시험이 비어도 초록이다. 둘 다 이 시험이 이전부터 가진 한계다.

**대기열:** 없음

**Status:** done

- [x] 같은 시험을 16개 동시에 돌린 부하에서 고치기 전에 16개 중 11개 빨갰던 것이 고친 뒤 16개 두 번과 32개 한 번 모두 초록이다
- [x] 이 PC가 한가할 때 그 시험을 홀로 돌려 초록이고, 리눅스 기대(`parse_timeout`, 기한 2초)는 그대로다
- [x] 근거를 돌려 볼 프로브와 출력이 `.scratch/harness/probes/parse_runner_stall_deadline/`에 있고 `.scratch/harness/probes/README.md` 표에 행이 있다
- [x] `CLAUDE.md`의 검증 명령(pytest, ruff 둘, pyright, lint-imports)이 초록이다
