# release-image 04: 설치 안내가 운영자를 묶음 풀기부터 MCP 검색과 업그레이드까지 이끈다 · 2026-11-20

release-image 티켓 여덟 가운데 다섯째로 구현한 티켓(`04-install-guide-walks-operator`)의 세션 기록이다. 시작 프롬프트는 `/implement .scratch/release-image/issues/04-install-guide-walks-operator.md`이고 브랜치는 `feature/04-install-guide-walks-operator`, 작업은 같은 이름의 워크트리에서 했다. 범위는 PR과 병합까지다. 모델은 Sonnet 5.5 / high이고 컨텍스트가 두 번 압축됐다. 준비, 한 일, 확인한 것, 셀프 리뷰, 검사, PR 직전 리뷰, 커밋을 차례로 두고, 봇 회차와 회고와 다음은 PR을 연 뒤에 잇는다.

## 준비

- 시작할 때 agent-os의 변경을 봤다. `git -C C:/project/agent fetch origin`과 `git -C C:/project/agent log b74a8adf2..origin/dev -- <티켓이 적은 경로 열 개>`가 둘 다 종료 0이고 출력이 비었다. 옮길 변경이 없어 사용자에게 묻지 않았다.
- `.env`는 훅이 직접 읽고 쓰는 것을 막는다. 가짜 값으로 채운 `.env`가 필요해 사용자에게 물었고, "임시 폴더에서 스크립트로 만들기"를 골랐다. 저장소 밖 스크래치의 스크립트가 `.env`를 만들고 고쳤다.
- 나란히 도는 05(노트 검사, PR 80)는 서로 독립이다. 이 세션이 일하는 동안 05가 `origin/dev`에 병합됐다(`f845ced`). 커밋한 뒤 `origin/dev`를 합친다.

## 한 일

- `deploy/standalone/README.md`(새 파일): 열네 절이다. 보증하는 환경과 메모리, 묶음 풀기, `.env`, 인증서(자체 서명 인증서를 만드는 명령, 키 파일의 `root:101`과 `0640`), 모델 폴더, 띄우기, 첫 인증 토큰, 문서 넣기, MCP로 접속하기, 서비스와 이미지의 대응표, 리랭커 켜기, 프록시 설정 고치기, 볼륨, 폐쇄망 설치, Docker Hub 받기 제한, 업그레이드(바꾸기, 띄우기, 되돌리기)다.
- `deploy/standalone/tls/README.txt`와 `deploy/standalone/models/README.txt`(새 파일): 인증서 폴더와 모델 폴더에 두는 것, 소유와 권한, 첫 시작이 모델을 내려받는다는 것, 시험한 리비전, 폐쇄망으로 옮기는 법.
- `README.md`(루트): 머리 문단과 이미지 절이 묶음의 설치 안내를 가리키게 고쳤다. bake 명령은 개발자의 짓기로 남겼다. 트리에 `tests/standalone/`와 `deploy/standalone/` 두 줄을 더했다(티켓 목록 밖이고 판 절 고침과 한 덩어리다).
- `tests/tools/test_deploy_guide.py`(새 파일): 안내와 묶음의 다른 파일이 어긋나지 않는지 보는 정합 시험 14개다. agent-os에는 옮길 파일이 없어(origin/dev에서 해당 경로의 변경이 없었다) 이 저장소의 사실로 새로 썼다.

## 확인한 것

- 안내의 명령을 개발 PC(Windows 10, Docker Desktop, Engine 29.9.2, Compose 5.6.1)에서 쳤다. 자체 서명 인증서, 모델 폴더와 `refs/main` 읽기, 띄우기, 첫 인증 토큰, 문서 넣기, MCP 검색, `nginx -t -c`와 `nginx -s reload -c`, 리랭커 켜기, 업그레이드와 되돌리기, 폐쇄망 설치 흉내까지다. 친 명령과 걸린 시간은 티켓 Comments에 적었다. 모델을 내려받는 데 409초, 이미지 다섯을 담는 데 48초(파일 약 1.6GiB), 모델 폴더를 묶는 데 압축 없이 57초(8.5GiB), `z`를 더하면 29분 26초(5.0GiB), 풀기 45초, 폐쇄망 띄우기 74초였다.
- 업그레이드: `proxy/` 안을 비우고 다시 채우면 옛 묶음에만 있던 파일이 남지 않았다. compose는 얹은 파일만 바뀐 프록시를 다시 만들지 않았고(컨테이너 번호와 시작 시각이 같았다), `nginx -s reload -c` 뒤에야 새 설정으로 답했다. 되돌리기(`--remove-orphans`)로 서버와 작업자가 옛 번호로 뜨고 프록시가 옛 설정으로 답했다.
- 폐쇄망: `docker load` 뒤 digest로 고정한 바깥 이미지가 이름 없이 올라오는 일이 있어(nginx에서 확인) 로컬 이름을 다시 붙이고 `compose.override.yaml`로 쓰게 하는 길을 안내에 정했다.
- 단독 compose 시험(`deploy/`를 고쳤으므로): 모델 폴더의 심볼릭 링크를 `cp -rL`로 푼 복사본으로 첫 실행은 마당에서 `WinError 3` 오류 25개, 다시 `25 passed in 206.86s (0:03:26)`였다.
- 못 잰 것: 최소 판(Engine 28.3.3, Compose 2.20.2), 바깥으로 나가는 길이 정말 없는 기계, 빈 폴더에서 폐쇄망 서버가 모델을 받으러 나가는 길, containerd 이미지 저장소, 리눅스의 파일 소유와 `sudo tar`다.

## 셀프 리뷰

`/code-review`를 기준 `origin/dev`로 돌렸다. 표준 축은 저장소 상태 시험이 변이 짝 없이 서 있는 것을 Major로 짚었고, 명세 축은 필수 낱말과 폐쇄망 `compose.override.yaml`의 서비스와 이름 짝맞춤 시험의 틈을 짚었다. 안내의 사실 문장은 주장마다 근거를 대 보고 고쳤다.

- 고친 것: ① 정합 검사 여덟(인증서 이름, 프록시 주 설정, 환경 변수 칸, 소유, 리비전, 폴더 설명, 고치지 말 것, 대응표)을 `묶음_파일` 값 하나로 읽게 모으고, 칸마다 한 군데를 바꾼 사본으로 같은 이름의 검사가 걸리는지 보는 변이 시험을 짝으로 뒀다. ② 폐쇄망 `compose.override.yaml`의 서비스와 로컬 이름의 짝맞춤을 검사하고 변이 사례(프록시에 tei 이름을 단 사본)를 뒀다. ③ 안내의 문장: 리랭커 프로필을 "빼는" 표현을 "관찰한 것"으로, `docker compose ps`가 끝난 `migrate`를 가리는 것, 메모리 값과 다시 잰 값, 키 권한 확인의 종료 코드, 모델 폴더가 끊긴 채 옮겨졌을 때의 추측("재지 않은 어림"으로 표시), containerd 서술, 단위.
- 남긴 것: 백업과 복원의 절차는 backup-upgrade가 정하는 일이라 안내에 아직 없다고 적었다. 리눅스에서 `sudo`가 든 명령은 이 PC에서 치지 못했다.
- 이 일지에 옮기기 전 티켓 Comments에 적은 두 문장(리랭커 검색 경로, 받은 리비전과 시험한 리비전이 같다)은 근거가 안내 본문에 없어 걷거나 낮췄다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 CodeRabbit CLI 0.7.5로 로컬 변경(기준 `origin/dev`, 파일 일곱 개, `origin/dev`를 합친 뒤)을 봤다. `Plan: Free`, `Seat: not assigned`였지만 `review_completed`까지 돌았고 한도 때문에 못 돈 일은 없다. CLI 지적은 셋이고 셋 모두 유효로 판정했다. 에이전트는 본 세션이 밀어 넣은 사실 문장 여섯도 대 봤고 모두 맞았다. 마이그레이션이 한 트랜잭션이라는 문장은 `env.py`가 `transaction_per_migration` 없이 `context.begin_transaction()`으로 전체를 묶는 것으로 읽었고, 일부러 실패시켜 보지는 않았다.

- 고친 것(셋 모두 안내): ① `cp -r proxy proxy.old`는 `proxy.old`가 이미 있으면 그 안의 `proxy.old/proxy/`로 들어가, 두 번째 업그레이드부터 되돌리기가 직전 버전이 아니라 두 버전 전의 설정을 복원하고 `proxy/proxy/`가 딸려 온다. 에이전트가 임시 폴더에서 쳐서 확인했다. 복사 전에 `rm -rf proxy.old`를 넣었다. ② 폐쇄망 업그레이드가 `compose.override.yaml`의 태그를 고치는데 바꾸기가 그 파일을 백업하지 않고 되돌리기가 복원하지 않아, 옛 `compose.yaml`이 새 바깥 이미지로 뜬다. 폐쇄망 설치는 `compose.override.yaml.old`로 백업하고 되돌릴 때 복원하게 적었다. ③ `sudo tar`의 `cf`와 `xf`에 `--numeric-owner`를 더했다(싣는 기계에 uid 10001이 아닌 같은 이름의 사용자가 있으면 이름으로 소유가 정해지는 길을 막는다).
- 고친 것(시험): 에이전트가 낸 Nit 셋을 받아들였다. `대응표_어긋남`과 `폐쇄망_어긋남`이 훑은 범위가 비면 실패하게 직접 단언을 더했고, 변이가 없던 가지(임베딩과 리랭커의 소유, 키 파일 이름, 모델 폴더 설명의 낱말)에 변이 사례를 더했다.
- 남긴 것: 없다. `tests/adapters/test_migrations.py`에 일부러 실패시키는 시험이 있는지는 에이전트도 제목만 봤고, 우리 안내의 문장은 "코드를 읽어 확인했고 일부러 실패시키지는 않았다"로 정직하게 적혀 있어 그대로 둔다.
- 고친 뒤 다시 돌릴 것: 시험, 린트, 포맷, 타입체크, 전체 검사 묶음. 결과는 아래 "검사"에 잇는다.

## 검사

- `uv run pytest tests/tools/test_deploy_guide.py`: `14 passed in 0.40s`.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run lint-imports`, `uv run pyright`: 모두 종료 0.
- `uv run python tools/run_checks.py`: 종료 0. `test-db`, `check-ticket`, `lint-imports`, `zizmor`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest`(413.5초)가 모두 통과했다. 티켓을 `done`으로 올리고 확인란을 모두 채운 상태에서 돌렸다.
- `origin/dev`(05 병합)를 합친 뒤 `tests/tools/test_deploy_guide.py`, `tests/tools/test_release.py`, `tests/test_plan_status.py`가 통과했고, 전체 검사 묶음도 종료 0이었다. 그 실행 도중에 PR 직전 리뷰의 고침이 파일을 바꾸었으므로 최종 판은 아래 커밋의 pre-commit이 갈음한다.
- PR 직전 리뷰를 반영한 뒤 `tests/tools/test_deploy_guide.py`: 통과, `ruff check`와 `pyright` 종료 0.
- `uv run python tools/plan_table.py`와 `uv run python tools/sibling_overlap.py`: 종료 0, 겹침 없음.

## 커밋

- `ecf72c2` 기능 커밋: pre-commit의 전체 검사가 통과했다.
- `9c546d8` 합치기: `origin/dev`(`f845ced`, 05)를 합쳤다. 충돌은 없었다.
- `5eeda90` PR 직전 리뷰 반영: pre-commit의 전체 검사가 통과했다.
- CodeRabbit 첫 리뷰 반영과 일지·대기열 커밋은 아래 "봇 회차" 뒤에 한 커밋으로 실었다.

## 봇 회차

PR은 [82](https://github.com/njh6803/rag-engine/pull/82)이고 base는 dev다. 머리 `5eeda90`에서 검사 열(`CodeRabbit`, `claude-review`, `eval-fast`, `eval-full`, `image`, `python`, `standalone`, `ticket`, `title`, `verify`)이 모두 성공이었다. `standalone` 잡은 base가 dev라 시험하지 않고 성공으로 끝났다(03과 같다).

- **claude-review.** 머리 `5eeda90`에서 지적 없음이었다.
- **CodeRabbit의 첫 리뷰.** `@coderabbitai review`를 남기자 `Finished`로 끝났다. 지적 둘(Major 하나, Minor 하나)이 인라인으로 달렸고 둘 다 코드에 대 보고 유효로 판정해 고쳤다.
  - **고친 것(Major).** 안내 14절 "되돌리기"가 "마이그레이션이 실패했을 때만 되돌릴 수 있다. 실패하면 스키마가 그대로 남는다"고 적었는데, `migrate_database()`(`src/rag_engine/adapters/postgres/bootstrap.py`)는 스키마를 올린 뒤에 따로 기본 레코드를 만든다. 임베딩 차원이 상한을 넘거나 모르는 청킹 전략을 적은 설정은 스키마가 오른 뒤에야 거절된다(그 파일의 주석이 같은 말을 한다). 그 경우 `migrate` 컨테이너는 실패하지만 스키마는 이미 올라 있어 되돌리면 옛 코드가 새 스키마와 함께 뜬다. 되돌리기 문단을 단계별 셋으로 나눴다. 스키마를 올리는 단계의 실패는 되돌린다, 기본 레코드 단계가 `.env`의 설정을 거절한 경우는 되돌리지 말고 `.env`를 고쳐 `docker compose run --rm migrate`를 다시 친다(9절에서 두 번 돌려도 오류 없이 끝난 것을 근거로 달았다), 단계를 가르지 못하거나 마이그레이션이 끝난 뒤의 실패는 업그레이드 전 백업에서 복원한다. 이 가름은 코드를 읽어 정했고 `migrate`를 일부러 실패시켜 보지는 않았다.
  - **고친 것(Minor).** `고치지_말_것_어긋남`이 프록시의 443 매핑 문자열이 있는지만 봐서, 다른 서비스에 `ports:`를 더해도 시험이 통과했다. compose의 모든 `ports:` 블록을 모아 `"0.0.0.0:443:8443"` 하나뿐인지 보게 했고, `5432:5432`를 더한 사본을 잡는 변이 사례를 더했다.
- **이후 회차.** CodeRabbit의 다음 리뷰부터는 둘째 회차라 Critical·Major만 고친다.

## 회고

후보 여섯을 냈고 판정은 승인 셋, 기각 셋, 넘김 없음이다. 대기열 만료 후보는 없다(`tools/queue_open_rows.py`가 "만료할 항목 (없음)"을 냈다). 일지는 `tools/sibling_overlap.py --journal`이 이 파일을 가리켰다.

1. **승인: `review-report-journal-lag` 9회차.** 사건은 이 세션이다. 셀프 리뷰 두 축의 보고를 받고 판정해 안내와 시험을 고쳤지만 그때까지 이 브랜치의 일지 파일이 없었다(`docs/journal/`에 2026-11-20 일지가 03 것 하나뿐이었다). 컨텍스트가 두 번 압축된 뒤 PR 직전에 일지를 처음 만들며 셀프 리뷰 절을 압축 요약이 담은 만큼으로 썼고 지적마다의 원문 판정은 일지에 없다. PR 직전 리뷰 보고는 보고 끝의 줄대로 받은 턴에 옮겼다. 이미 있는 지침(`code-review` 6단계 끝, `merge.md` 3)을 어긴 사건이라 회차로 센다. 항목은 이미 5회차를 넘어 chore 배치의 계기다.
2. **승인: `repo-state-test-without-mutation-partner` 1회차(새 항목).** 사건은 이 세션이다. 안내와 묶음의 다른 파일을 맞대는 시험 파일을 처음 쓸 때 저장소 상태 시험 여럿을 `.claude/rules/tests.md`가 요구하는 변이 시험 짝 없이 세웠고, 셀프 리뷰 표준 축이 Major로 잡았다. 구현 때 실리는 규칙을 어겨 리뷰가 잡은 사건이라 회차로 센다. 처방은 `tools/check_instructions.py`에 이름 짝을 보는 검사를 두는 것이고(검사가 판정할 수 있는 것은 검사로), 더하는 것이라 다섯 번째에 반영한다.
3. **승인: `standalone-models-symlink-note` 1회차(새 항목).** 사건은 이 세션이다. `deploy/`를 고친 뒤 단독 compose 시험을 모델이 든 폴더 그대로 돌렸더니 마당이 `WinError 3`으로 `25 errors in 46.81s`를 냈고, 링크를 푼 복사본(`cp -rL`)으로 `25 passed in 206.86s`를 얻었다. 같은 처치가 03의 Comments와 일지에 있었지만 시험 독스트링과 04로 넘긴 "다음"에는 없었다. 처방은 독스트링 한 문장이나 마당의 복사 방식 고침이고, 더하는 것이라 다섯 번째에 반영한다.
4. **기각: 이미 있는 훅이 그 자리에서 막거나 알린 것들.** 맨 `python`, 파이프로 이은 게이트 명령, `.env`에 닿는 넓은 grep, 작업 폴더 가드가 거절한 heredoc, 한국어 지침 훅의 알림이다. 막힌 뒤 바로 고쳤다.
5. **기각: 리뷰가 제 몫을 한 것.** PR 직전 리뷰가 낸 안내의 빈틈 셋(`proxy.old`가 있을 때 복사본이 안으로 들어가는 것, 폐쇄망 설치의 되돌리기가 `compose.override.yaml`을 복원하지 않는 것, `tar`의 소유를 이름으로 정하는 것)이다. 개발 PC에서 첫 업그레이드만 쳐 보고 두 번째 업그레이드와 폐쇄망 되돌리기를 치지 않아 생긴 틈이고, 리뷰가 잡아 고쳤다. 같은 종류가 여러 번 나는지는 이 항목들이 반복될 때 본다.
6. **기각: 압축 뒤 요약에 기대 쓴 티켓 Comments의 두 문장.** "리랭커 검색이 리랭커를 거쳤다"와 "받은 리비전이 시험한 리비전과 같다"는 안내 본문이 뒷받침하지 않는 말이었다. 커밋 전에 Comments를 안내 본문과 대 보다가 내가 잡아 걷고 낮췄다. 리뷰가 잡은 사건이 아니라 이 셈에서 뺀다. `measured-claim-beyond-probe`(15회차)와 같은 종류라 그 항목이 이미 chore 배치의 계기다.

반영 자리는 모두 대기열이다. 이 세션에서는 하네스를 고치지 않았고 항목 파일 하나의 줄과 새 항목 파일 둘만 더했다.

## 다음

이 PR(base dev)은 제품의 배포 파일 묶음에 드는 안내와 시험을 더하지만 계약의 칸이나 헌법을 바꾸지 않는다. 병합 뒤 release-image의 티켓 여덟 가운데 일곱(01~07)이 닫히고 08(`08-ci-releases-from-main`)만 `ready-for-agent`로 남는다. 08은 막는 티켓이 모두 `done`이라 열리고, 이 기능의 마지막 티켓이다. 08이 끝 줄(`**끝:**`)과 기능 단락과 첫 릴리스의 소개 글을 싣고, 그 병합 뒤 결정표의 "출시 PR"이 계기가 된다.

08이 04에서 받을 것은 다음과 같다.

- 08의 "저장소 상태 시험"이 견주려는 것 가운데 bake 설정의 저장소 이름과 단독 compose의 `image:` 줄과 설치 안내의 대응표는 04의 `tests/tools/test_deploy_guide.py`의 `대응표_어긋남`이 이미 맞댄다(bake에 `/<저장소>:`가 있는지, 안내 표에 `<이름공간>/<저장소>`가 있는지, compose의 우리 이미지가 서버 둘과 작업자 하나인지). 08은 그 견줌을 다시 쓰지 않고 이 시험을 가리키며, 08이 더하는 둘(`FROM`과 compose 바깥 이미지의 digest 고정, 프록시 `/mcp`의 `proxy_buffering off`)만 새로 쓴다.
- 안내는 폐쇄망 설치에서 digest로 고정한 바깥 이미지 셋에 `rag-engine-offline/<nginx|pgvector|tei>:<digest 앞 12자>` 이름을 붙이고, 이 이름과 digest의 짝을 `폐쇄망_어긋남`이 compose와 맞댄다. 바깥 이미지의 digest를 바꾸는 변경(08이 아니라 다른 티켓)은 안내의 `docker tag` 줄과 `compose.override.yaml` 블록을 함께 고쳐야 시험이 초록이다.
- 리눅스에서 처음 도는 것은 이 기능의 출시 PR이다. 그때 안내의 `sudo chown`(키 파일 `root:101`, 모델 폴더 `10001:10001`)과 `sudo tar --numeric-owner`, 모델 폴더 크기가 처음 리눅스에서 밟힌다. 개발 PC(Windows)에서는 재지 못했다.
- 단독 compose 시험을 개발 PC에서 돌릴 때 모델 폴더를 그대로 넘기면 마당이 `WinError 3`으로 끝난다. 링크를 푼 복사본(`cp -rL`)을 `RAG_STANDALONE_MODELS`로 넘긴다(대기열 `standalone-models-symlink-note`).
- 설치 안내는 최소 판(Engine 28.3.3, Compose 2.20.2)에서 재지 않았다고 적었다. 08이 첫 릴리스에서 그 판으로 띄워 볼 길은 없다.

뒤로 넘긴 일은 둘이다. 첫째, 백업과 복원의 절차는 backup-upgrade가 정한다고 안내가 적었다. 그 기능이 열리면 안내의 14절 머리와 "되돌리기"가 가리키는 자리를 함께 고친다. 둘째, 폐쇄망 설치의 되돌리기(`compose.override.yaml.old` 복원)는 개발 PC에서 치지 못했다. 세션 경계와 병합은 `next-session` 스킬의 `merge.md`를 따른다.
