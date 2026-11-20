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
