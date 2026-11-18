# 03: 단독 compose가 프록시 뒤에 다섯 컨테이너를 띄우고, 시험이 운영자의 차례를 그대로 밟는다

**What to build:** `deploy/standalone/`에 단독 compose(이 서버만 따로 설치하는 구성. compose 파일 하나로 검색 서버, 작업자, 그리고 그 둘이 쓰는 서비스까지 함께 띄운다)의 `compose.yaml`, `.env.example`, 프록시 설정 `proxy/nginx.conf`와 `proxy/site.conf`가 선다. 운영자가 `.env`를 채우고 `tls/`에 인증서를 두고 `docker compose up -d --wait --wait-timeout 1800`을 치면 프록시(nginx), 검색 서버, 작업자, PostgreSQL, 임베딩 서버가 차례대로 뜨고(그 앞에 마이그레이션이 한 번 돈다), 밖으로 열린 포트는 프록시의 443 하나다(스토리 5~10, 12~22, 40).

단독 compose 시험이 이 차례를 그대로 밟는다. 01의 이미지 둘과 02의 도구로 지은 배포 파일 묶음을 받아, 진짜 임베딩 서버로 띄우고, 관리 명령으로 표본 문서를 넣고, 공식 MCP SDK 클라이언트로 443에 접속해 검색한다. `ci.yml`에 그 시험 잡을 더하되 base가 main인 PR과 main 푸시에서만 시험한다(스토리 42~45).

근거는 명세 "단독 compose", "프록시", "이미지의 구성"의 읽기 전용 루트·`/tmp`·헬스체크 항목, "배포 파일 묶음"의 `.env.example` 항목 둘, "ci.yml"의 단독 compose 시험 잡 항목, Testing Decisions의 단독 compose 시험 항목 전부다. 원형은 `.scratch/release-image/probes/standalone/`의 `run.py`와 시제품 compose·프록시 설정이고(같은 폴더 README 표), 명세가 든 수치는 그 프로브의 단계(`up`, `sse`, `checks`, `recover`, `offline`, `download`, `accept`)가 잰 것이다.

**Blocked by:** 01 (이미지 둘과 bake 설정), 02 (묶음을 짓는 도구)

**Status:** ready-for-agent

### 단독 compose와 프록시

- [ ] 시작할 때 agent-os의 변경을 본다. `git -C C:/project/agent fetch origin` 뒤에 `git -C C:/project/agent log b74a8adf2..origin/dev -- .github/workflows/release.yml tools/release.py tools/release_ci.py tools/check_notes.py deploy/ tests/tools/test_release.py tests/tools/test_release_ci.py tests/tools/test_release_workflow.py tests/tools/test_check_notes.py tests/tools/test_deploy_guide.py`가 비지 않으면 그 변경을 함께 옮길지 사용자에게 묻고 멈춘다(명세 "따르는 것과 옮기는 방식"). 두 명령 가운데 하나라도 오류로 끝나면 빈 출력으로 보지 않고 그 오류를 보고하고 멈춘다. 바뀐 파일이 이 티켓이 옮기는 파일이 아니면 묻지 않고 그 커밋을 Comments에 적고 잇는다. 사용자에게 물었으면 그 답과 본 agent-os 커밋을 Comments에 적는다. 기점이 `1aac0cf`가 아니라 `b74a8adf2`인 까닭은 명세 "따르는 것과 옮기는 방식"이 적는다. 옮길 것은 그 커밋의 `deploy/standalone/compose.yaml`, `.env.example`, `proxy/`이고, agent-os 제품의 서비스(위젯, 관리 화면)는 옮기지 않는다.
- [ ] `compose.yaml`은 명세 "단독 compose"의 항목을 모두 싣는다. 최상위 `name: rag-engine`(볼륨 이름이 `rag-engine_postgres`와 `rag-engine_data`가 된다), 서비스 이름(`proxy`, `postgres`, `embedding`, `migrate`, `server`, `worker`, 프로필 `reranker`의 `reranker`), `.env`의 값으로 고르는 이미지와 비면 멈추는 넷(`RAG_ENGINE_NAMESPACE`, `RAG_ENGINE_VERSION`, `RAG_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`의 `${이름:?문구}` 꼴), `env_file`과 compose가 덮어쓰는 셋(`RAG_DATABASE_URL`, `RAG_DATA_DIR`, `RAG_DEFAULT_EMBEDDING_URL`. 리랭커 끝점은 compose가 주지 않는다), 볼륨 둘과 모델 폴더, 띄우는 차례(`service_healthy`, `service_completed_successfully`. `worker`는 `embedding`도 기다린다), 재시작 정책, IPv6를 끈 기본 네트워크, `0.0.0.0:443:8443`, digest로 고정한 바깥 이미지 셋, 임베딩 서버의 인자(`compose.eval.yml`과 같은 `--model-id BAAI/bge-m3 --port 80 --max-batch-tokens 4096`)·사용자·읽기 전용 루트·시작 유예 30분, 서버·작업자·마이그레이션의 읽기 전용 루트와 `/tmp`(서버는 `${RAG_ENGINE_SERVER_TMP_SIZE:-1g}`), 파이썬 표준 라이브러리로 `/health`를 보는 헬스체크, 프록시 컨테이너의 권한 줄이기다. 임베딩 서버의 리비전 고정, `HF_HUB_OFFLINE`, 로그 설정은 두지 않는다(명세의 `[거절]`과 `[정함]`).
- [ ] 리랭커 서비스는 임베딩 서버와 같은 꼴이다. 모델은 `BAAI/bge-reranker-v2-m3`(ADR 0010)이고, uid 10001, 읽기 전용 루트, `/tmp`의 tmpfs, 쓸 수 있게 붙인 `models/reranker/`, 시작 유예 30분이다. 명세가 재지 않은 리랭커의 인자(배치 크기 같은 것)와 메모리는 개발 PC에서 프로필로 한 번 띄워 정하고, 띄운 명령과 `docker stats`로 본 메모리를 Comments에 적는다. 04가 그 값을 설치 안내의 리랭커 절에 옮긴다. `docker compose --profile reranker config`가 종료 0인지는 시험이 본다.
- [ ] 최소 판 Compose 2.20.2에서 이 `compose.yaml`이 뜨는지 본다. 한 번 돌고 끝나는 `migrate`를 `service_completed_successfully`로 기다리게 둔 채 `up -d --wait --wait-timeout 1800`이 성공으로 돌아오는지와, 그 판이 `--wait-timeout`을 받는지다(명세 "설치 안내"의 최소 판 항목). 그 판의 compose를 구할 길(공식 배포물)과 친 명령과 결과를 Comments에 적는다. 안 되면 멈추고, 최소 판을 바꿀지 사용자에게 묻는다. 그 판을 구하지 못하면 그 까닭을 적고 04에 "최소 판에서는 재지 않았다"를 그대로 두게 넘긴다.
- [ ] 프록시 설정은 명세 "프록시"의 항목을 모두 싣는다. 넘기는 경로 넷(`= /mcp`, `/api/v1/ingest/`, `/api/v1/admin/`, `= /health`)과 빗금 없는 두 경로의 정확 일치 404, 나머지 404, TLS 1.2와 1.3, HSTS 머리, 사용자가 고른 접근 로그의 칸(시각, 보낸 주소, 메서드, `$uri`, 상태 코드, 걸린 시간), 사이트의 `error_log /dev/null`, 넘기는 머리 셋, 올리는 본문을 막거나 모으지 않는 설정, `/mcp`의 응답을 모으지 않는 설정, 뒷단 이름을 5초마다 다시 푸는 설정, `proxy_read_timeout` 기본값이다. 인증서 이름은 `tls/fullchain.pem`과 `tls/privkey.pem`이다.
- [ ] 프록시의 주 설정을 얹는 자리(compose의 `proxy` 서비스가 `command`의 `-c`로 주는 경로)를 이 티켓이 정한다. 04가 설치 안내의 `nginx -t -c <주 설정>`과 `nginx -s reload -c <주 설정>`에 그 경로를 옮긴다(명세 "프록시"의 설정을 고친 뒤 항목).
- [ ] `.env.example`은 표지 `@RAG_ENGINE_NAMESPACE@`와 `@RAG_ENGINE_VERSION@`을 담고(02의 도구가 채운다), 운영자가 꼭 채우는 둘(`RAG_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`)을 빈 값으로 두며, 쓰는 곳이 없는 `RAG_DELETED_RETENTION_DAYS`는 넣지 않는다(명세 "배포 파일 묶음"). `FORWARDED_ALLOW_IPS`도 넣지 않는다(명세 "프록시"의 서버가 `X-Forwarded-*`를 믿지 않는 항목). 서버 `/tmp`의 크기(`RAG_ENGINE_SERVER_TMP_SIZE`)와 리랭커를 켜는 설치의 `RAG_DEFAULT_RERANKER_URL=http://reranker:80`은 주석 처리한 예시 줄로 둔다.

### 단독 compose 시험

- [ ] 실패하는 시험을 먼저 쓴다. 시험은 pytest로 쓰고 기본 수집에서 뺀다. `uv run pytest --collect-only -q`의 출력에 그 시험이 없고 건너뛴 시험으로도 세지 않으며(원칙 I), 경로를 주어 칠 때만 모이는 것을 손으로 보고 Comments에 적는다. 시험은 시작할 때 443이 비었는지 보고, 차 있으면 까닭을 적고 실패한다.
- [ ] 시험은 이미지를 환경 변수 둘(이름공간과 번호)로 받고, 없으면 bake 설정으로 직접 짓는다(이름공간 `rag-engine-test`, 번호 `0.1.0-rc.1`). 배포 파일 묶음도 환경 변수로 받고, 없으면 02의 도구로 `deploy/standalone/`에서 짓는다. 모델 폴더도 환경 변수로 받고, 없으면 명세 "단독 compose"의 명령대로 풀어 둔 묶음 안에 `models/embedding/`을 만들어 uid 10001에게 주고 임베딩 서버의 첫 시작이 내려받게 한다. 묶음에는 그 폴더가 없다. 리눅스에서는 `sudo` 대신 같은 일을 하는 컨테이너(`chown`만 하는 것)를 써도 되고, Windows의 Docker Desktop은 바인드 마운트의 소유를 흉내 내므로 그 단계가 Windows에서 무엇을 하는지(또는 건너뛰는지) 시험의 독스트링에 적는다. 이 단계의 소유 문제는 리눅스 러너에서 처음 드러난다. 변수 이름은 이 티켓이 정하고 시험의 독스트링에 적는다. 08의 릴리스 워크플로가 그 이름으로 부른다. 04의 정합 시험이 안내의 명령과 대 볼 수 있게, 시험이 치는 띄우는 명령·인증서 명령·모델 폴더 명령은 한 자리(상수)에 둔다.
- [ ] 시험이 밟는 차례와 확인하는 것은 명세 Testing Decisions의 두 항목("시험이 밟는 차례", "시험이 확인하는 것") 그대로다. 띄우는 명령은 설치 안내와 같은 `docker compose up -d --wait --wait-timeout 1800`이다. 확인 목록의 항목(빈 필수 값의 `docker compose config`, 띄운 직후의 첫 `/health`, 리랭커 프로필의 `config`, 서버 프로세스를 죽인 뒤와 서버 컨테이너를 다시 만든 뒤 15초 안의 200, PostgreSQL 로그를 포함한다)을 모두 단언으로 둔다. PostgreSQL 로그에 질의나 표본 문서의 글이 나오면 단언을 느슨하게 고치지 않고 멈춰 보고한다(원칙 V. 명세가 재지 않은 자리다).
- [ ] 시험은 실행마다 새로 만드는 자리만 쓴다(명세 Testing Decisions의 그 항목). 상태와 인증서는 `tmp_path`에, compose 프로젝트와 볼륨의 이름은 실행마다 무작위 꼬리를 붙여 짓고 이미 있으면 실패하며, 대조 스택은 다른 프로젝트 이름을 쓰고, `down -v`는 그 호출이 띄운 프로젝트에만 친다. 설정을 바꿔 띄우는 대조 단계는 저마다 `finally`에서 되돌린다. 프로브 `run.py`가 이 규칙을 지키지 않은 자리(명세가 든 다섯)를 옮기지 않는다.
- [ ] 시험이 부르는 외부 명령(docker, docker compose)에는 호출마다 시간 제한을 둔다. 띄우는 명령은 그 명령의 기다림(1800초)보다 긴 제한을 받는다.
- [ ] 어떤 설정에서도 초록이 되는 단언이 둘 있었으므로 조건을 지킨다(명세 Testing Decisions). TLS 1.1 확인은 클라이언트의 보안 수준을 낮춰(`SECLEVEL=0`) 1.1을 내밀 수 있게 한 채 한다. 서버 컨테이너를 다시 만드는 확인은 옛 주소를 다른 컨테이너가 차지하게 한 채 한다(프로브 `run.py`의 `recover` 단계가 그렇게 했다).
- [ ] 확인 목록이 어떤 설정에서도 초록인 단언이 아닌지 본다. 단언 가운데 적어도 둘(예: 프록시가 `/docs`를 넘기게 한 설정, 접근 로그에 `$request_uri`를 남기게 한 설정)을 일부러 깨뜨린 사본으로 시험이 빨개지는 것을 손으로 보고 Comments에 적는다. 깨뜨린 사본은 커밋하지 않는다.

### 명세가 재지 않은 것

- [ ] 실제 서버의 `/mcp` 응답이 프록시를 지나 이어 보내는 꼴(`Content-Type: text/event-stream`)로 오는지와 `X-Accel-Buffering` 머리가 바깥에 없는지를, 단독 compose를 띄운 채 손으로 보고 명령과 함께 Comments에 적는다. 명세의 측정은 가짜 뒷단으로 했다(프로브 `sse` 단계). 지금 서버에 진행 알림처럼 사건을 여럿 보내는 응답이 없으면, 사건 사이가 모이지 않는다는 것은 가짜 뒷단 측정에 기댄다고 적는다(명세 "프록시"의 `/mcp` 항목).
- [ ] 사이트 설정의 `error_log /dev/null`이 요청을 처리하다 난 오류(`crit` 줄을 포함한다)를 모두 받아, 주 설정의 오류 로그(`notice`)로 요청 줄이 새지 않는지를 nginx 문서의 `error_log` 지시어(쓸 수 있는 문맥과 아래 문맥으로 물려주는 규칙)를 원문으로 읽고 읽은 자리를 Comments에 적는다. 명세는 `crit` 줄을 재지 않았다(명세 "프록시"의 접근 로그 항목).
- [ ] 임베딩 서버가 거절한 요청의 로그는 확인 목록의 단언(표지 글을 담은 꼴이 틀린 본문을 보낸 뒤 그 글이 로그에 없다)으로 다시 본다. 토큰 상한을 넘는 글은 `--max-batch-tokens 4096`에서 TEI가 잘라 200으로 답하므로 거절이 되지 않는다(명세 "단독 compose"의 로그 항목, 명세 검토의 손 확인). 거절이 실제로 났는지(422)도 함께 단언해, 거절되지 않은 요청으로 초록이 되지 않게 한다.

### CI

- [ ] `ci.yml`에 단독 compose 시험 잡을 더한다. 잡은 늘 시작하고, 첫 스텝(gate)이 base가 main인 PR과 main 푸시에서만 시험하게 정하며, 그 밖(dev로 가는 PR, dev 푸시, 수동 실행)에서는 나머지 스텝을 스텝의 조건으로 건너뛴 채 성공으로 끝난다. `verify`의 `needs`에 잡 이름만 더한다(명세 "ci.yml", ADR 0020 "느린 시험이 도는 자리"). 선례는 `eval-full` 잡의 첫 스텝이다.
- [ ] 임베딩 모델 폴더는 `eval-fast` 잡과 같은 캐시 키(`eval-tei-<모델>-<TEI 판>`)로 복원만 하고(저장은 `eval-fast`가 맡는다. `ci.yml`의 `eval-full` 머리 주석과 같은 까닭이다), 캐시가 없으면 임베딩 서버의 첫 시작이 내려받는다. 복원한 뒤에는 캐시가 있든 없든 그 폴더를 만들어 uid 10001에게 주고(`mkdir -p`와 `sudo chown -R 10001:10001`) 시험에 넘긴다. `eval-fast`가 캐시를 러너 사용자의 것으로 저장하고, 캐시가 없을 때의 빈 폴더는 uid 10001이 쓸 수 없기 때문이다(명세 "릴리스 워크플로"의 시험 단계 항목). 잡의 제한 시간은 캐시가 없는 경우(이미지 짓기, 모델 내려받기, 1800초까지의 기다림)를 넘게 잡는다(명세 Testing Decisions). 어림으로 60분 언저리에서 시작하고 잡 옆 주석에 그 셈을 적는다(`ci.yml` 머리 주석의 관례). agent-os의 20분을 옮기지 않는다. 시험이 실패하면 남긴 로그를 산출물로 올린다.
- [ ] 이 PR(base dev)의 CI에서 그 잡이 시험하지 않고 성공으로 끝나며 `verify`가 초록인 것을 실행의 주소로 Comments에 적는다. 리눅스 러너에서 시험이 처음 도는 것은 이 기능의 출시 PR이다(명세 Further Notes).
- [ ] 개발 PC에서 경로를 주어 시험을 끝까지 한 번 돌리고, 결과와 걸린 시간(모델이 든 폴더와 빈 폴더 가운데 쓴 것)을 Comments에 적는다(스토리 44).
- [ ] 검사 넷이 초록이다.
