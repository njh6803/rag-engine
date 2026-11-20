# 핫픽스 standalone-stop-test-timeout: 서버가 멈춘 동안의 요청을 기다리는 시간을 프록시의 504보다 길게 고친다 · 2026-11-21

첫 릴리스의 첫 시도가 `build` 잡의 단독 compose 시험 가운데 서버 정지 시험에서 졌고, 앞 핫픽스(`standalone-test-fills-image-namespace`)를 마친 같은 세션에서 이어 고쳤다. 브랜치는 `hotfix/standalone-stop-test-timeout`(기준 `origin/main`, `e464535`), 작업은 `08-ci-releases-from-main` 워크트리에서 했다. 모델은 Sonnet 5.5 / high이다. 제품 코드와 프록시 설정은 바꾸지 않았다. 준비, 한 일, 확인한 것, 셀프 리뷰, 회고, 다음을 차례로 둔다.

## 준비

- 첫 시도의 로그에서 읽은 것(손으로 읽었고 프로브는 없다): 서버 정지 시험이 `assert status in (502, 503, 504)`에서 `status=None`으로 졌다. 프록시의 504는 요청을 보낸 지 60.026초에 났고 시험 클라이언트의 제한 `HTTP_TIMEOUT`은 60.0초였다. 러너의 Docker DNS가 멈춘 `server` 이름에 약 30초 간격으로 SERVFAIL을 돌려줬다. 같은 실행의 `--failed` 재실행은 모두 통과했고 PR의 CI `standalone` 잡도 두 번 통과했다.
- 60초가 `proxy_connect_timeout`과 `proxy_read_timeout` 가운데 어느 쪽인지는 가리지 않았다. 둘의 기본값이 같고 프록시 설정(`deploy/standalone/proxy/`의 `.conf` 전부)에 `proxy_*timeout` 줄이 없다. DNS 지연이 요청을 붙잡았다는 인과는 확인하지 않은 추정이다.

## 한 일

- `tests/standalone/test_standalone_compose.py`: 상수 `STOPPED_SERVER_TIMEOUT`(90초)을 더했다. `request`, `get`, `marked_get`가 `timeout`을 받고 주지 않으면 `HTTP_TIMEOUT`(60초)이다. 서버 정지 시험만 `marked_get(stack, timeout=STOPPED_SERVER_TIMEOUT)`으로 부른다.
- `tests/tools/test_standalone_env.py`: Docker 없이 도는 시험 셋을 더했다. 프록시 설정에 `proxy_*timeout` 줄이 없다는 단언(훑은 `.conf`가 비면 실패한다), 서버 정지의 기다림이 프록시 기본 60초보다 10초 이상 길다는 단언, `get`에 준 `timeout`이 요청까지 전해지고 주지 않으면 `HTTP_TIMEOUT`이 쓰인다는 단언이다.
- `.scratch/harness/issues/standalone-stop-test-timeout.md`: 티켓과 Comments.
- `release.yml`, `ci.yml`, 프록시 설정은 바꾸지 않았다.

## 확인한 것

- 고치기 전에 새 시험 둘이 빨갰다. `STOPPED_SERVER_TIMEOUT`이 없다는 `AttributeError`와 `get`이 `timeout`을 받지 않는다는 `TypeError`다(`uv run pytest tests/tools/test_standalone_env.py`, `2 failed, 6 passed`). 고친 뒤 `8 passed`(두 번: 65.94초, 셀프 리뷰 반영 뒤 119.90초. 다른 세션이 이 PC를 쓰는 때라 시간이 흔들린다).
- `ruff check .`, `ruff format --check .`, `pyright`(오류 0), `lint-imports`(2 kept), `tools/check_type_escapes.py`, `tools/plan_table.py --check`가 초록이다. 테스트 전체는 커밋의 pre-commit이 갈음한다.
- 이 PC에서 Docker로 서버 정지 시험을 돌리지 않았다. 고친 간헐 실패는 러너의 DNS가 느린 때에만 나서 이 PC에서 만들지 못한다. 서버 정지 시험이 실제로 도는 모습은 그 시험을 띄워야 알 수 있다. Docker 없는 시험은 값의 관계, `get`과 `marked_get`의 전달, 서버 정지 시험의 소스에 그 인자가 있는지까지 지킨다(PR 직전 리뷰 뒤에 더한 둘은 아래 절).

## 셀프 리뷰

`/code-review`를 기준 `origin/main`(`e464535`)으로 돌렸다. 범위는 고친 파일 둘, 새 파일 하나(티켓), 커밋 없음이다. 표준 축은 표준 위반 0과 Minor 셋, Nit 둘을, 명세 축은 누락 0, 범위 넘침 0과 틀려 보이는 것 하나를 냈다.

- 고친 것: ① 티켓과 시험 주석이 504가 `proxy_read_timeout`에서 났다고 단정했다. 두 보고가 함께 짚었다. 둘 다 60초 기본값이라 값은 맞고 이름이 불확실해서 `proxy_connect_timeout`과 `proxy_read_timeout`을 함께 적고 어느 쪽이 걸렸는지는 가리지 않았다고 고쳤다. 티켓의 "DNS가 요청을 붙잡는다"도 확인하지 않은 추정으로 낮췄다. ② 설정 검사가 `site.conf`만 훑던 것을 프록시 폴더의 `.conf` 전부로 넓히고 훑은 범위가 비면 실패하게 했다. ③ `done` 티켓에 병합 뒤에 볼 열린 체크박스가 남던 것을 Comments의 "병합 뒤에 볼 것"으로 옮겼다.
- 남긴 것: 상수 `PROXY_UPSTREAM_TIMEOUT`(nginx 기본값)과 `HTTP_TIMEOUT`(시험 클라이언트 제한)이 같은 60.0을 따로 적는 것은 뜻이 달라 일부러 나눴다. `Stack`을 손으로 채우는 시험은 필드가 늘면 깨지지만 그 깨짐이 알림 구실을 해서 뒀다. 서버를 다시 띄운 직후 `until_ready(stack, 60)`의 요청마다 60초 제한은 이번 실패의 자리가 아니라 건드리지 않고 티켓 Comments에 적었다. 90초에도 504가 안 오는 경우는 같은 `status=None`으로 진다. 그 고침은 프록시 `proxy_connect_timeout`을 줄이는 제품 쪽 변경이라 이 핫픽스 밖이다(티켓 Comments).
- 다시 돌린 것: 위 `확인한 것`의 검사. 전체 리뷰는 다시 돌리지 않았다.

## 커밋과 PR 직전 리뷰

커밋 `9c7f4dc`는 pre-commit을 처음 시도에서 통과했다(전체 pytest 616.8초, 다른 검사 모두 통과). 이어 PR 직전 리뷰를 돌렸다. CodeRabbit CLI는 앞 핫픽스에서 권한 분류기가 거절해 이번에도 쓰지 않고, 버그·성능 축은 `bug-perf-review`로, 보안 축은 내장 `/security-review`로 봤다.

- 보안 축: 지적 없음. 변경이 시험 코드와 문서뿐이고 입력 처리, 인증, 암호, 외부 호출 경로가 바뀌지 않았다.
- 버그·성능 축: Critical·Major 없음, Minor 하나와 Nit 하나. 주석의 nginx 60초 문장, 설정 검사, 티켓과 일지의 사실 문장(시험 이름, 숫자, 잡 이름)은 코드와 맞는다고 확인했다.
  - Minor(고침): 서버 정지 시험이 `STOPPED_SERVER_TIMEOUT`을 쓰는지를 어느 시험도 지키지 않았다. 누가 `marked_get`의 `timeout=timeout`이나 서버 정지 시험의 인자를 빼도 Docker 없는 시험 셋이 초록이라 같은 간헐 실패가 돌아올 수 있었다. 시험 둘을 더했다. `marked_get`이 `timeout`을 `get`까지 전하는지 보는 시험과, 서버 정지 시험 함수의 소스에 `marked_get(stack, timeout=STOPPED_SERVER_TIMEOUT)`이 있는지 보는 시험이다. 뒤의 것은 인자를 일부러 뺀 사본에서 빨개지는 것을 확인하고 되돌렸다. 더한 뒤 `10 passed`(125.08초).
  - Nit(고침): 상수 주석이 러너 DNS 지연을 단정처럼 적던 것에 "추정"을 붙였다.
- 남긴 것: 서버 정지 시험의 최악 시간은 8 + 90 + 1초에 정리의 `until_ready(60)`을 더해 약 4분이고, CI 제한(`ci.yml` 60분, `release.yml` 90분) 안이다. 리눅스에서는 이 PC에서 돌려 보지 못했다(경로와 모듈 이름에 리눅스에서 막힐 것은 없다고 읽었다).
- 다시 돌린 것: `ruff check .`, `ruff format --check .`, `pyright`(오류 0)가 초록이다. 이 고침 커밋의 테스트는 pre-commit이 갈음한다.

## 회고

후보 둘, 승인 0, 기각 2, 넘김 0.

- 같은 값 둘이 겹쳐 간헐로 지는 제한 시간(기각): 사건은 이 세션에 있으나 이 핫픽스가 이미 Docker 없는 시험으로 그 관계를 고정했고(층: 시험), 같은 꼴의 다른 사례는 아직 없다. 더할 것이 없다.
- 병합 뒤 첫 릴리스에서만 드러나는 길(기각): 대기열 항목 `release-workflow-first-run-on-main`이 이미 처방한다. 이번 실패는 병합 전 CI `standalone` 잡에서 두 번 통과한 시험이 러너의 DNS 지연으로 한 번 진 것이라, 밟지 않은 길이 아니고 그 항목의 회차로 세지 않았다. 부하와 환경에서만 지는 시간 시험은 사용자가 닫은 종류라(2026-11-15) 일지에만 적는다.

## 다음

- 이 PR을 main에 병합한다. 병합 뒤 릴리스를 기다리고(`next-session merge.md`의 "릴리스를 기다린다"), 끝나면 main을 dev에 합친다.
- 남은 사람 몫은 없다.
