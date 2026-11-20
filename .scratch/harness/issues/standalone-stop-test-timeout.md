# standalone-stop-test-timeout: 서버가 멈춘 동안의 요청을 기다리는 시간을 프록시가 504를 내는 시간보다 길게 고친다(핫픽스)

**What to build:** 첫 릴리스 실행 https://github.com/njh6803/rag-engine/actions/runs/44756889367 의 첫 시도에서 `build` 잡의 단독 compose 시험 가운데 `test_서버가_멈춘_동안에도_질의_문자열의_표지가_프록시_로그에_남지_않는다`가 `assert status in (502, 503, 504)`에서 `status=None`으로 졌다. 같은 실행의 `--failed` 재실행은 이 시험을 포함해 모두 통과했고, 같은 시험이 PR의 CI(`standalone` 잡)에서는 두 번 통과했다. 실행 로그와 컨테이너 로그에서 읽은 것은 둘이다(손으로 읽었고 프로브는 없다). 러너의 Docker DNS가 멈춘 `server` 이름에 약 30초 간격으로 SERVFAIL을 돌려줬고(`deploy/standalone/proxy/site.conf`의 `resolver 127.0.0.11 valid=5s`가 그 서버를 쓴다), 프록시의 504는 요청을 보낸 지 60.026초에 났다. 시험의 요청 제한 `HTTP_TIMEOUT`도 60.0초라 504가 닿기 전에 클라이언트가 먼저 끊었다. 읽은 값에서 해석한 것은 다음이다. 60초는 nginx 기본 제한(`proxy_connect_timeout`과 `proxy_read_timeout`의 기본값이 같고 어느 쪽이 걸렸는지는 가리지 않았다)이고, 러너의 DNS가 늦을 때 요청이 그 제한까지 갔다. DNS 지연이 요청을 붙잡았다는 인과는 확인하지 않은 추정이다. 어느 쪽이든 두 값이 같으면 간헐로 지는 구조이고, 이 PC에서는 되풀이하지 않았다.

고치는 곳은 `tests/standalone/test_standalone_compose.py`다. 서버가 멈춘 동안의 요청만 새 상수 `STOPPED_SERVER_TIMEOUT`(90초)으로 기다리고, 다른 요청의 `HTTP_TIMEOUT`(60초)은 그대로 둔다. 이를 위해 `request`, `get`, `marked_get`가 `timeout`을 받는다. 프록시 설정과 제품 코드는 바꾸지 않는다. 60초는 운영자가 받는 프록시의 동작이고 시험이 그 동작을 재는 것이어서, 시험 쪽에서 기다림만 늘린다.

**대기열:** 없음

**Status:** done

- [x] 고치기 전에 실패하는 시험이 있다: `tests/tools/test_standalone_env.py`에서 `STOPPED_SERVER_TIMEOUT`이 없다는 `AttributeError`와 `get`이 `timeout`을 받지 않는다는 `TypeError`로 빨갰다
- [x] 서버가 멈춘 동안의 기다림이 프록시의 기본 60초보다 10초 이상 길다고 Docker 없이 단언한다. 프록시 설정이 `proxy_*_timeout`을 정하면 그 전제가 틀어지므로 설정에 그런 줄이 없다는 단언도 같이 둔다
- [x] `get`과 `marked_get`에 준 `timeout`이 요청까지 그대로 전해지고, 주지 않으면 `HTTP_TIMEOUT`이 쓰인다고 Docker 없이 단언한다
- [x] 서버 정지 시험이 `marked_get`에 `STOPPED_SERVER_TIMEOUT`을 준다. 그 시험 함수를 가짜 의존물로 Docker 없이 직접 불러, `marked_get`이 받은 `timeout`이 그 상수인지 단언한다(인자를 뺀 사본에서 빨개지는 것을 확인했다)
- [x] 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(테스트는 커밋의 pre-commit이 갈음한다)

## Comments

- **병합 뒤에 볼 것.** 이 PR을 main에 병합하면 릴리스 워크플로가 다시 돌고, 단독 시험을 지나는지는 그 실행에서 본다. 이 티켓의 수용 기준은 병합 전에 채울 수 있는 것만 든다.
- **셀프 리뷰에서 남긴 Nit.** 상수 두 개(`PROXY_UPSTREAM_TIMEOUT`과 `HTTP_TIMEOUT`)가 같은 숫자 60.0을 따로 적는 것은 뜻이 달라서(앞은 nginx의 기본값, 뒤는 시험 클라이언트의 제한) 일부러 나눴다. `Stack`을 손으로 채우는 시험은 필드가 늘면 깨지지만, 그 깨짐이 이 시험에 필드를 알리는 구실을 해서 둔다.
- **이 PC에서 Docker로 서버 정지 시험을 돌리지 않았다.** 이 고침이 막는 것은 러너의 DNS가 느린 때에만 나는 간헐 실패이고, 이 PC에서는 그 조건을 만들지 못한다. 그래서 확인은 Docker 없이 도는 시험 셋(`tests/tools/test_standalone_env.py`)과 값의 관계(90초 대 프록시 60초)까지다. 서버 정지 시험이 실제로 도는 모습(서버를 멈추고 프록시의 504를 받는 것)은 그 시험을 띄워야 알 수 있다. Docker 없는 시험은 `get`과 `marked_get`의 전달, 그리고 서버 정지 시험 함수를 가짜 의존물로 불렀을 때 `marked_get`이 그 상수를 받는지까지 지킨다.
- **봇 첫 회차(2026-11-21).** claude-review의 Minor는 서버 정지 시험의 소스 글자를 찾던 시험이 구현을 복제한다는 것이었고, 가짜 의존물로 함수를 직접 부르는 시험으로 바꿨다. CodeRabbit의 Minor는 프록시 설정 검사가 줄 머리가 `proxy_`인 것만 봐서 `location /slow { proxy_read_timeout 120s; }`처럼 블록과 같은 줄에 쓴 제한을 놓친다는 것이었고, 주석을 뺀 글에서 `proxy_…timeout` 낱말을 찾는 함수로 바꾸고 놓치던 입력을 잡는 시험과 주석뿐인 입력이 지나는 시험을 더했다.
- **남긴 것(셀프 리뷰).** 서버를 다시 띄운 직후의 `until_ready(stack, 60)`도 요청마다 `HTTP_TIMEOUT` 60초를 쓴다. 막 뜬 서버에 프록시가 옛 이름 풀이를 붙들고 있으면 물음 하나가 60초를 쓸 수 있다. 이 시험의 단언은 `is not None`뿐이고 이번 간헐 실패의 자리가 아니어서 건드리지 않았다. 같은 자리가 다음에 지면 `until_ready`의 요청 제한을 따로 보자.
- **남기는 위험.** 90초 동안 기다려도 504가 오지 않으면(러너 DNS가 60초를 훨씬 넘겨 붙잡으면) 같은 `status=None`으로 진다. 그때는 프록시에 `proxy_connect_timeout`을 짧게 주는 것이 제품 쪽 고침이고, 운영자가 받는 동작이 바뀌므로 이 핫픽스에서 하지 않았다.
