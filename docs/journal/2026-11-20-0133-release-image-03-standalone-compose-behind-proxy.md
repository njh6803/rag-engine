# release-image 03: 단독 compose가 프록시 뒤에 컨테이너를 띄우고, 시험이 운영자의 차례를 그대로 밟는다 · 2026-11-20

release-image 티켓 여덟 가운데 넷째로 구현한 티켓(`03-standalone-compose-behind-proxy`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/03-standalone-compose-behind-proxy.md`이고 브랜치는 `feature/03-standalone-compose-behind-proxy`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 한 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, PR 직전 리뷰, 커밋, 봇 회차, 회고, 다음을 차례로 둔다.

## 준비

- 지시문대로 `tidy-checkouts`를 돌고 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 맞췄다. 나란히 도는 티켓 05(`05-notes-check-guards-upgrade-bang`)와는 서로 독립이다. 05도 `.github/workflows/ci.yml`을 고쳐서 `tools/sibling_overlap.py`가 겹치는 파일로 알렸고, 글자 충돌은 늦게 병합하는 쪽이 푼다.
- 시작할 때 agent-os의 변경을 봤다. `git -C C:/project/agent log --oneline b74a8adf2..origin/dev -- <티켓이 적은 경로>`가 비었다(origin/dev `148c86d08`). 옮길 변경이 없어 사용자에게 묻지 않았다.
- 이 PC의 Docker Compose는 v5.6.1이고 Docker가 쓸 수 있는 메모리는 15.6GiB다. 이 숫자가 리랭커 인자를 정하는 근거가 됐다.

## 한 일

티켓의 확인란 서른세 줄을 모두 채웠다(CI 실행 주소 한 줄만 PR의 CI가 돈 뒤에 채운다).

- `deploy/standalone/compose.yaml`: 서비스는 `proxy`, `postgres`, `embedding`, `migrate`, `server`, `worker`, 프로필 `reranker`의 `reranker`다. 최상위 이름 `rag-engine`, 필수 값 넷(`RAG_ENGINE_NAMESPACE`, `RAG_ENGINE_VERSION`, `RAG_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`)은 비면 멈춘다. 밖으로 열리는 포트는 프록시의 `0.0.0.0:443:8443` 하나다. 띄우는 차례는 PostgreSQL 건강 → 마이그레이션 끝 → 서버와 작업자(작업자는 임베딩 서버도 기다린다) → 프록시(서버가 건강해진 뒤)다. 바깥 이미지 셋(nginx, pgvector, TEI)은 digest로 고정했다.
- `deploy/standalone/proxy/nginx.conf`와 `site.conf`: 주 설정은 `/etc/rag-engine/proxy/nginx.conf`이고 compose가 `-c`로 준다(04가 설치 안내에 옮길 경로). 넘기는 경로는 `= /mcp`, `/api/v1/ingest/`, `/api/v1/admin/`, `= /health` 넷이고 나머지는 404다. TLS 1.2와 1.3, HSTS, 질의 문자열이 없는 접근 로그, 사이트의 `error_log /dev/null`, 뒷단 이름을 5초마다 다시 푸는 설정을 실었다.
- `deploy/standalone/.env.example`: 표지 둘, 빈 필수 값 둘, 주석 처리한 예시 둘.
- `tests/standalone/test_standalone_compose.py`(새 파일): 운영자가 하는 차례(묶음 풀기, `.env` 채우기, 인증서, 모델 폴더, `up -d --wait --wait-timeout 1800`)를 그대로 밟고 공식 MCP SDK 클라이언트로 443에 접속해 검색하는 시험 24개다. `pyproject.toml`의 `norecursedirs`로 기본 수집에서 빼고 경로를 주어 칠 때만 모은다.
- `.github/workflows/ci.yml`: `standalone` 잡. 늘 시작하고 체크아웃 다음 스텝(gate)이 base가 main인 PR과 main 푸시에서만 시험하게 정한다. `verify.needs`에 이름만 더했고 머리 주석의 잡 개수를 여섯으로 고쳤다.

## 확인한 것

- 빨강을 먼저 봤다. `deploy/standalone/`이 없을 때 시험은 마당(fixture)에서 오류로 끝났다. 배포 파일을 쓴 뒤 24개가 초록이 됐다.
- 개발 PC에서 끝까지 돌린 결과는 `24 passed in 161.64s`였고, 리랭커 인자를 고친 뒤 `223.37s`, 셀프 리뷰를 반영한 뒤 `350.00s`였다. 건너뛴 시험은 없다. 모델은 Docker 볼륨 `rag-latency-probe_tei-data`에서 `models--BAAI--bge-m3`만 링크를 풀어 복사한 폴더를 썼다.
- 일부러 깨뜨린 사본으로 시험이 빨개지는 것을 셋 봤다. `/docs`를 넘기게 한 설정과 접근 로그의 `$request_uri`(4개 빨강), `error_log /dev/null`을 뺀 설정(서버를 멈춘 채 보내는 요청 시험이 빨강), `ssl_protocols`에 1.1을 넣은 설정(셀프 리뷰 뒤에 더한 단언이 빨강). 깨뜨린 사본은 모두 되돌렸고 커밋하지 않았다.
- 손으로 본 것: 실제 서버의 `/mcp` 응답이 프록시를 지나도 `text/event-stream`, `transfer-encoding: chunked`이고 `X-Accel-Buffering`은 없다. 리랭커는 `--max-batch-tokens 4096`일 때 5.838GiB(같이 뜬 임베딩 서버는 5.169GiB)이고, 인자 없이 띄운 시도는 두 번 다 끝나지 않았으며 까닭은 가리지 못했다.
- nginx 문서(`ngx_core_module.html#error_log`)를 `curl`로 받아 본문을 읽었다. 문맥 사이로 물려주는 규칙은 거기 없어, `error_log /dev/null`이 요청 줄의 유출을 막는지는 깨뜨린 사본의 시험으로 갈음했다.
- 최소 판 Compose 2.20.2에서는 재지 못했다. 실행 파일을 내려받는 일은 사용자의 허락이 있어야 해서 받지 않았고, 04에 "최소 판에서는 재지 않았다"를 그대로 두게 넘겼다.
- 회복 시간 15초 단언은 서버 프로세스를 죽이는 시험에서 이 PC의 손으로 본 값이 8.0초와 9.5초였고(커밋하지 않은 임시 출력), 깨뜨린 사본으로 전체를 느리게 돌린 실행에서 19.2초가 나와 빨개진 적이 있다. 서버 컨테이너를 지우고 다시 만드는 시험의 값은 적지 않았다. 명세의 수치라 시험에서 늘리지 않았다.

## 셀프 리뷰

`/code-review`를 기준 `fa85261`(파일 8개, 커밋 0개, 미추적 0개)으로 돌렸다. 표준 축에서 Major 셋과 Minor 다섯, 명세 축에서 Major 없이 Minor 여럿이 나왔다. 지적마다 코드와 문서에 대 보고 판정했다.

- 고친 것: ① 리눅스에서 TLS 대조 서버가 스택의 키(`root:101`, `0640`)를 읽다 `PermissionError`가 나는 길을, 대조 서버가 자기 인증서를 새로 만들게 해 없앴다(이 PC는 Windows라 그 소유 변경이 건너뛰어져 안 보였다). ② `asyncio.run()` 직접 호출 둘을 `async def` 시험으로 바꿨다. ③ 없음을 `-1.0`·`0`으로 나타내던 곳을 `None`으로 바꿨다. ④ `compose.yaml`의 머리 주석과 리랭커 주석을 사실에 맞췄다. ⑤ 티켓 Comments의 `쟀다`와 `12GiB 안팎`을 손으로 본 값과 `11GiB 안팎`으로 고쳤다. ⑥ 시험 독스트링의 `finally` 서술과 `MODEL_FOLDER_COMMANDS` 설명을 고쳤다. ⑦ PostgreSQL과 임베딩 서버 로그가 비어 있지 않다는 단언을 더했다. ⑧ TLS 1.1 단언이 nginx 설정과 무관하게 초록이던 것을, 실행 중인 프록시에서 `nginx -T -c`로 `ssl_protocols` 줄을 읽어 맞대는 단언으로 보강했다(깨뜨린 사본에서 이 단언이 빨개졌다).
- 남긴 것과 이유: 회복 시간 15초가 `tests.md`의 "홀로 돌린 시간의 넉넉한 배수" 규칙과 어긋나는 것은 명세가 정한 수치라 그대로 두고, 까닭과 관찰한 시간을 `RECOVERY_SECONDS` 옆 주석과 티켓 Comments에 적었다. 냄새로 나온 `docker compose -p` 중복과 `(directory, namespace, version)` 묶음은 판단 항목이고 시험 파일 하나 안의 일이라 고치지 않았다.
- 다시 돌린 것: 저장소 전체의 `ruff check`, `ruff format --check`, `pyright tests/standalone`이 통과했다. 전체 검사는 아래 "커밋"의 pre-commit이 갈음했다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 CodeRabbit CLI 0.7.5로 로컬 변경(기준 `origin/dev`, 파일 8개)을 보안·버그·성능 축으로 봤다. `Plan: Free`, `Seat: not assigned`였지만 리뷰가 끝까지 돌았다. CLI의 지적은 둘이었고(유효 하나, 오탐 하나), 에이전트가 본 세션이 지정한 다섯 사실 문장을 직접 대 본 것에서 보류 하나와 주석 서술 어긋남 둘이 더 나왔다. 지적마다 코드와 명세에 대 보고 판정했다. 보고를 받은 턴에 일지로 옮기지 못하고 컨텍스트가 압축되어, 이 절은 회고 단계에서 서브에이전트의 원 보고와 대 보며 다시 썼다.

- 고친 것: ① `stack` 마당의 `finally`가 `save_logs`를 먼저 부르고, 그 호출이 예외를 내면 `down -v`, 도우미 컨테이너 제거, 소유 되돌리기가 모두 건너뛰어졌다. 남은 컨테이너와 볼륨은 다음 실행의 443을 막는다. 로그 저장을 안쪽 `try`로 감싸 뒤의 정리가 늘 돌게 했다. ② `until_ready`의 독스트링이 제한 안에 200이 없으면 `None`이라고만 적었는데, 제한은 다음 물음을 시작할지만 정하므로 마지막 물음이 제한을 넘겨 200을 받으면 제한보다 큰 값이 돌아온다. 그 사실을 적었다. 회복 시험 둘(`seconds is not None and seconds <= RECOVERY_SECONDS`)은 늦게 돌아온 200을 실패로 세고, `until_ready(stack, 30)`과 `until_ready(stack, 60)`을 쓰는 단언 둘은 결국 돌아오기만 보므로 제한을 다시 견주지 않는다. 독스트링이 그 가름을 적는다. ③ `RECOVERY_SECONDS` 옆 주석에 서술이 둘 어긋나 있었다. 19.2초를 다른 일이 겹친 실행이라고 적었지만 티켓은 깨뜨린 사본으로 전체를 느리게 돌린 실행이라고 적는다. 8.0초와 9.5초를 홀로 돌린 값이라고 적었지만 티켓은 커밋하지 않은 임시 출력으로 두 번 손으로 봤다고만 적고 홀로 돌렸다는 말이 없다. 이 값들은 모두 서버 프로세스를 죽이는 시험의 값이고, 서버 컨테이너를 지우고 다시 만드는 시험의 값은 티켓에 없다. 주석을 티켓의 말로 맞췄다. 처음 반영에서는 첫째 어긋남만 고치고 둘째를 놓쳐, 이 회고에서 원 보고와 대 보다가 잡아 고쳤다. ④ `ci.yml`의 `standalone` 잡 주석이 gate를 첫 스텝이라고 적었는데 첫 스텝은 체크아웃이다. 체크아웃 다음 스텝으로 고쳤다. 일지 본문의 같은 문구 둘도 함께 고쳤다.
- 오탐으로 판정해 남긴 것: 회복 시험의 15초를 서버 컨테이너를 다시 만들기 시작한 시각부터 재라는 제안(CLI의 지적)이다. 명세(`.scratch/release-image/spec.md`)가 서버 컨테이너를 지우고 다시 만든 뒤 서버가 건강해지면 프록시가 15초 안에 200을 낸다고 적어서, `up --wait`가 건강해질 때까지 기다린 뒤부터 재는 지금 방식이 명세 그대로다. 시작 시각부터 재면 시험이 명세의 수치를 바꾸게 된다.
- 대 본 사실 문장 다섯: `serve_only`와 소유 설명, TLS 주석과 `nginx -T` 단언, `compose.yaml`의 리랭커 값과 머리 주석은 맞았다(`ssl_protocols` 줄이 정확히 한 줄이라는 것과 `user:`가 프록시 101, 임베딩 서버·리랭커 10001에만 있다는 것을 파일에서 읽었다). `RECOVERY_SECONDS` 주석과 `ci.yml` 주석은 위 ③과 ④가 어긋나 있었다. `ci.yml`의 제한 시간 셈(이미지 빌드 10분, 대기 30분, 시험 10분)은 이미지 빌드 10분을 측정으로 확인할 수 없어 보고가 맞는지 단정하지 않았다.
- 다시 돌린 것: `ruff check`, `ruff format --check .`, `pyright tests/standalone`이 통과했다. 시험 24개는 다시 돌리지 않았다. 고친 곳은 정리 순서의 감싸기, 독스트링, 주석, 워크플로 주석이라 시험의 판정을 바꾸지 않는다. 전체 검사는 아래 커밋의 pre-commit이 갈음한다.

## 커밋

- `912d3e2` 기능 커밋: pre-commit의 `ruff check`, `ruff format`, 병렬 검사(`test-db`, `check-ticket`, `lint-imports`, `zizmor`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest` 466.5초), 표 검사, 줄 구분자 검사, 변이 표 검사, 따옴표 인용 대조(경고만), 커밋 메시지 검사가 모두 통과했다.
- `78c21e6` 티켓 Comments의 따옴표 인용을 풀어쓴 문서 커밋. 인용 대조 경고 다섯이 모두 내가 쓴 문구에 붙인 따옴표여서 원문이 있는 인용이 아니었고, 따옴표를 뗐다.
- 합치기: `origin/dev`(`ed395e7`, 리뷰 봇 지시문의 판)를 이 브랜치에 합쳤다. 충돌은 없었고 `tests/test_plan_status.py`는 13개가 통과했다.

## 봇 회차

PR은 [81](https://github.com/njh6803/rag-engine/pull/81)이고 base는 dev다. 머리 `dccb944`에서 검사 아홉(`python`, `image`, `eval-fast`, `eval-full`, `ticket`, `standalone`, `verify`, claude-review, CodeRabbit)을 읽었다.

- **첫 회차.** claude-review는 지적 없음이었다(경계, 원칙 IV·V, 제목 접두를 봤다고 적었다). CodeRabbit은 `@coderabbitai review`를 남긴 뒤에도 무료 한도에 걸려 리뷰를 내지 않았다(`Review rate limited`, 다음 리뷰는 37분 뒤). 그래서 이 PR에서 CodeRabbit의 첫 리뷰는 아직 없고, 로컬에서 CodeRabbit CLI로 돈 PR 직전 리뷰가 그 자리를 대신한다.
- **반영한 것 없음.** 고칠 지적이 없어 반영 커밋은 없다. 이 절과 티켓의 CI 확인란, 아래 회고와 "다음"만 일지 커밋으로 푸시한다.
- **`standalone` 잡.** base가 dev라 gate 스텝만 성공이고 나머지를 모두 건너뛴 채 12초에 성공으로 끝났다(`gh run view --json jobs`로 스텝별로 읽었다). `verify`도 초록이다. 주소는 티켓 Comments에 적었다. 리눅스 러너에서 시험이 처음 도는 것은 이 기능의 출시 PR(dev에서 main으로 가는 PR)이다.

## 회고

후보 여섯을 냈고 판정은 승인 셋, 기각 셋, 넘김 없음이다. 대기열 만료 후보는 없다(`tools/queue_open_rows.py`가 "만료할 항목 (없음)"을 냈다). 일지는 `tools/sibling_overlap.py --journal`이 이 파일을 가리켰다.

1. **승인: `review-report-journal-lag` 8회차.** 사건은 이 세션이다. `coderabbit-review`의 보고를 받고 지적을 판정한 턴에 일지로 옮기지 못한 채 컨텍스트가 압축되었다. 압축 요약만 보고 쓴 "PR 직전 리뷰" 절에 보고에 없던 지적(기본 인자로 띄운 리랭커)이 들어갔고, 보고가 짚은 주석 서술 어긋남 둘 가운데 "홀로 돌렸다"는 말을 놓쳐 새 주석과 일지와 PR 본문에 그대로 옮겼다. 이 회고에서 서브에이전트의 출력 파일을 열어 원 보고와 대 보고서야 잡았고, 주석, 일지, PR 본문을 고쳤다. 이미 있는 지침(`code-review` 6단계 끝, `merge.md` 3, 보고 끝에 달린 줄)을 어긴 사건이라 회차로 센다. 항목은 이미 5회차를 넘어 chore 배치의 계기이고, 이번에 적은 사실은 같은 원인인데 이번에는 틀린 서술이 PR 본문까지 올라갔다는 것이다.
2. **승인: `crlf-from-script-edits` 11회차.** 사건은 이 세션이다. 새로 만든 시험 파일의 작업 사본이 922줄 모두 CRLF였고 `git add`의 경고로야 알았다. 같은 세션의 `compose.yaml`은 LF였고, `tools/rewrap_comments.py`는 코드를 읽어 보니 줄 끝을 새로 만들지 않는 것으로 읽혀(돌려 본 것은 아니다) 어느 단계가 CRLF를 만들었는지는 가리지 못했다. 앞의 회차와 원인이 다를 수 있으나, 처방(작업 사본의 CRLF를 알리는 검사)은 원인과 관계없이 같아서 같은 항목에 세었다. 손상은 없다(커밋은 git이 LF로 정규화했다). `sed -i`로 LF로 되돌렸다.
3. **승인: `pre-pr-review-missing-from-implement-path` 1회차(새 항목).** 사건은 이 세션이다. 범위가 PR과 병합까지였는데 PR 직전 리뷰를 건너뛰고 푸시하려다, 병합 절차와 `operations.md`를 읽으며 알아채고 푸시 전에 에이전트를 돌렸다. `implement` 스킬에서 `coderabbit|PR 직전`을 찾으면 일치가 없다. PR 서식의 체크리스트가 같은 단계를 묻는 자리라 손상은 없다. 더하는 것이라 다섯 번째에 반영하고 그 전에는 회차를 센다. 같은 단계의 다른 건너뜀은 `security-review-skipped-on-docs-pr`다.
4. **기각: 리뷰가 제 몫을 한 것들.** `stack` 마당의 `finally`에서 로그 저장의 예외가 정리를 건너뛰게 한 것(PR 직전 리뷰), 손으로 본 값을 쟀다고 적은 것과 12GiB 안팎의 서술(셀프 리뷰의 주장 검증 7번), `ssl_protocols` 단언이 nginx와 무관하게 초록이던 것과 키 읽기 권한(셀프 리뷰)이다. 모두 `code-review`가 잡도록 둔 기준이고 리뷰가 잡아 고쳤다. 이 셈에서 뺀다. `measured-claim-beyond-probe`(15회차)도 이 사건으로 더하지 않았다. `finally`의 정리 순서는 표준에 올릴 둘째 사건이 아니다.
5. **기각: 이미 있는 훅과 검사가 그 자리에서 막거나 알린 것들.** 하위 폴더로 `cd`하거나 한 호출에 길게 묶은 명령을 막은 훅, 한글 폭 때문에 줄 길이가 넘은 것을 알린 ruff 훅, `.env`에 닿는 glob을 막은 훅, 제 문구에 붙인 따옴표를 경고한 따옴표 대조다. 막히거나 알린 뒤 바로 고쳤다.
6. **기각: 회복 시간 15초가 `tests.md`의 시간 단언 규칙과 어긋난 것.** 명세가 운영자에게 약속한 수치와 규칙이 부딪힌 것이고 새 실수가 아니다. 까닭과 값은 `RECOVERY_SECONDS` 옆 주석과 티켓 Comments에 적었고, 러너에서 흔들리면 명세의 수치를 사용자가 다시 정하게 했다.

반영 자리는 모두 대기열이다. 이 세션에서는 하네스를 고치지 않았고 항목 파일 둘의 줄과 새 항목 파일 하나만 더했다.

## 다음

이 PR(base dev)은 제품의 배포 파일을 더하지만 계약의 칸이나 헌법을 바꾸지 않는다. 병합 뒤 release-image의 프런티어에서 03이 빠지므로 04(설치 안내)가 열린다. 05(노트 검사)는 PR 80이 열려 있어 그 세션의 몫이다. 08은 01부터 07까지가 모두 닫힌 뒤이므로 04와 05가 병합된 다음이다.

04가 설치 안내에 그대로 옮길 것을 03의 결과로 적는다. 프록시의 주 설정 경로는 컨테이너 안의 `/etc/rag-engine/proxy/nginx.conf`이고 compose가 `-c`로 준다. 설정을 고친 뒤에는 같은 경로를 `-c`로 주어 `nginx -t`와 `nginx -s reload`를 친다. 리랭커는 `--profile reranker`로 켜고 `--max-batch-tokens 4096`을 준다(5.838GiB는 손으로 본 값이고 같이 뜬 임베딩 서버는 5.169GiB다. 인자 없이 띄운 시도는 두 번 다 끝나지 않았고 까닭은 가리지 못했다). 서버의 임시 폴더 크기는 `.env`의 `RAG_ENGINE_SERVER_TMP_SIZE`가 바꾼다. 모델 폴더의 소유와 권한 명령은 시험 파일의 `MODEL_FOLDER_COMMANDS` 주석이 설치 안내용 기록이다. 최소 판 Docker Compose 2.20.2에서는 재지 못했으니 04가 "최소 판에서는 재지 않았다"를 그대로 둔다.

뒤로 넘긴 일은 셋이다. 첫째, 이 시험이 리눅스 러너에서 처음 도는 것은 이 기능의 출시 PR이다. 그때 모델 폴더의 소유 바꾸기, 키 파일 권한, uid 101이 `/dev/stdout`을 여는 길을 처음 밟는다. 둘째, 서버 컨테이너를 지우고 다시 만드는 시험의 15초 상한은 명세의 수치라 시험에서 늘리지 않았다. 러너에서 흔들리면 08이 첫 CI 실행에서 보고 사용자에게 올려 명세에서 다시 정한다. 셋째, CodeRabbit이 이 PR에서 무료 한도에 걸려 리뷰를 내지 못했다(`Review rate limited`). 이 PR의 리뷰는 로컬 CodeRabbit CLI(PR 직전)와 claude-review(지적 없음)가 맡았다. 05의 PR 80이 먼저 병합되면 `ci.yml`의 글자 충돌이 날 수 있어, 늦게 병합하는 쪽이 푸는 규칙대로 병합 전에 `origin/dev`를 합친다. 세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
