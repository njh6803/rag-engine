# source-sync 15: 단독 compose와 설치 안내 · 2026-11-25

source-sync 티켓 14를 병합한 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/15-standalone-sources-mount.md`이고, 브랜치는 `feature/15-standalone-sources-mount`, 작업은 워크트리 `15-standalone-sources-mount`에서 했다. 요청 범위는 PR과 병합까지다. 이 기능의 마지막 티켓이다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 15, 명세 `.scratch/source-sync/spec.md`의 "단독 compose와 설치 안내"(385~402행)와 "동기화의 차례"의 끝없는 목록 항목, 티켓 14 일지의 "다음", 설치 안내와 정합 시험(`tests/tools/test_deploy_guide.py`), 단독 compose 시험.
- 지시문이 시킨 순서: 주 체크아웃이 낡아 `tidy-checkouts`를 먼저 돌고(루트를 당기고 병합된 워크트리와 브랜치를 지웠다. 휴지통 `empty-trash`는 `.pyd` 접근 거부(WinError 5)로 종료 1이었고 그 보고에만 적었다. `14-reindex-version-switch`는 사람에게 넘겼다), `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다.

## 지은 것

- **`deploy/standalone/compose.yaml`.** 서버와 작업자의 `volumes`에 `${RAG_ENGINE_SOURCES_DIR:-./sources}:/sources:ro`를 더했다. 마이그레이션에는 붙이지 않았고 전파 설정(`rslave`)도 넣지 않았다. compose가 정하는 값에 `RAG_SOURCES_DIR: /sources`를 더해 `.env`가 덮어쓰지 못하게 했다(머리 주석의 "아래 셋"이 "아래 넷"이 됐다).
- **`deploy/standalone/sources/README.txt`(새 파일).** 이 폴더 아래에 원천마다 하위 폴더를 만들고, 바로 아래의 파일은 어느 원천에도 들지 않는다는 것을 적었다. 빈 폴더는 묶음에 담기지 않아 이 파일이 폴더를 묶음에 싣는다.
- **`.env.example`.** 주석 처리한 예시 줄 다섯(`RAG_ENGINE_SOURCES_DIR`, `RAG_SCHEDULE_TIMEZONE`, `RAG_DELETED_RETENTION_DAYS`, `RAG_SYNC_RECORD_RETENTION_DAYS`, `RAG_SOURCE_READ_TIMEOUT_SECONDS`). 티켓 14의 "다음"이 넘긴 둘이 여기에 든다.
- **설치 안내(`README.md`).** 6절에 하위 절 "서버 폴더의 문서 가져오기"를 더했다. 원천 폴더 만들기와 권한, 공유 폴더를 붙이는 때와 다시 띄우는 명령, SMB는 `hard` 없이 붙이기, 원천을 만들고 확인하고 동기화하고 기록을 보는 예시 명령, 일정과 시간대, 동기화가 문서를 지우지 않는 경우와 길(`apply_empty`, `reread`, 빈 폴더, 원천 지우기), 느린 공유 폴더, 끊긴 공유 폴더의 차례 셋과 곁 설명 셋, 원천을 지우고 되살리기, 끝나지 않는 동기화를 멈추는 차례, `ingest`로 `default`에 넣어 둔 폴더를 원천으로 옮기는 절차를 적었다. 3절의 값 셋을 넷으로, 11절과 14절에 `sources/`를 더했다. 2절 폴더 목록에도 한 줄 더했다(요구한 네 군데 밖이다).
- **시험.** `tests/tools/test_deploy_guide.py`에 정합 검사 "원천 폴더"를 더했다(server·worker의 마운트, 마이그레이션에 없음, `RAG_SOURCES_DIR` 고정, 전파 설정 없음, `.env.example` 예시 줄 다섯과 그 값이 `Settings`의 기본값과 같은지, 안내의 값 넷, `sources/README.txt`의 낱말). 변이 시험을 열두 개 더했다. `tests/standalone/test_standalone_compose.py`에 장면 하나를 더했다: `sources/regulations/leave.pdf`를 두고 띄워 원천을 만들고 지금 동기화하면 기록이 `succeeded`(받은 1, 더한 1)이고 MCP 검색에 그 문서가 나오며, 서버와 작업자의 `/sources`가 읽기 전용이라 쓰기가 `EROFS`로 막히고, 마이그레이션에는 `/sources`가 없고, 호스트에 쓰기 흔적이 없다.
- **끝 줄과 기능 단락.** `.scratch/source-sync/plan.md`에 `**끝:** 2026-11-25`, `docs/release-notes/features/source-sync.md`(한 단락, 328자), `uv run python tools/plan_table.py`로 계획 표를 다시 만들었다(source-sync가 done이 되고 프론티어가 `admin`, `backup-upgrade`, `diag-bundle`이 됐다).

## 이 세션이 정한 것

- **빈 폴더 동기화는 문서가 없는 원천에서는 성공으로 끝난다.** 처음 안내는 "빈 폴더면 늘 실패"라고 적었으나, 임시 스택에서 쳐 보니 문서가 아직 없는 원천은 `succeeded`(`listed` 0)였다. `_guard_empty_list`가 그 원천에 지워지지 않은 문서가 있을 때만 막는다. 안내를 코드에 맞췄다.
- **`RAG_MAX_UPLOAD_MB`는 `env_file`로 컨테이너에 닿는다.** 티켓 04의 일지가 15에 넘긴 물음이다. `compose config`로 서버, 작업자, 마이그레이션에 모두 실리는 것을 보았다(티켓 Comments).
- **정합 시험이 예시 값과 `Settings` 기본값을 같이 본다.** `.env.example`의 "적지 않으면 이 값"이라는 주석이 틀려도 시험이 못 잡았던 구멍(아래 셀프 리뷰 Major 1)을 막으려는 것이다.

## 겪은 것

- **`bootstrap-token`은 살아 있는 관리 토큰이 있으면 새로 내지 않는다.** 예시 명령을 쳐 보려고 시험이 풀어 둔 묶음으로 스택을 다시 띄웠더니 첫 실행의 토큰이 출력에서 빠져 두 번째 실행이 401이었다. 임시 스택의 `tokens` 표에서 `revoked_at`을 적고 다시 냈다(도구가 낸 안내 그대로다). 임시 스택이라 `down -v`로 지웠다.
- **Windows의 Git Bash가 명령 인자를 바꿨다.** 한글이 든 `curl -d` 본문은 400 `There was an error parsing the body`였고(UTF-8 파일로 `--data-binary @파일`을 보내면 200), `-v /import:ro`의 `/import`는 `C:/Program Files/Git/import`로 바뀌었다(`MSYS_NO_PATHCONV=1`). 둘 다 이 PC의 셸 탓이고 안내의 명령은 바꾸지 않았다. 또 `curl -o /tmp/out.txt`가 같은 환경 변수 아래에서는 Git의 `/tmp`가 아니라 `C:\tmp`에 써서 목록 조회 결과가 앞 실행의 것으로 찍혔다. 그 뒤 쪽의 결과 표는 리다이렉트로 다시 받은 것만 적었다.
- **시험을 돌리는 시간이 길다.** 정합 시험은 26개에 372초(이미지 묶음을 짓는 시험이 겹친 때), 단독 compose 시험은 26개에 733초였다. 홀로 다시 돌린 정합 시험은 66초였다.

## 검증

- **단독 compose 시험(`uv run pytest tests/standalone -q`).** 새 장면을 더한 뒤 26개 통과(733초). 셀프 리뷰를 반영한 뒤 `-x`로 한 번 더 돌렸을 때는 23개 통과 뒤 `test_서버_프로세스를_죽이면_컨테이너가_다시_떠_15초_안에_200이다`가 19.1초로 15초 상한을 넘어 실패하고 멈췄다. 원천 폴더와 무관한 시간 단언이고, 그때 이 PC에서 CodeRabbit CLI 리뷰와 정합 시험이 함께 돌고 있었다. 다른 작업 없이 `-x` 없이 전체를 다시 돌리니 26개가 모두 통과했다(486초, 종료 코드 0). 부하 때문에 시간 시험이 한 번 빨갛고 홀로 돌리면 초록인 종류라 새 사례는 이 줄에만 적는다(부하 시간 시험 종류는 닫힌 채 둔다).
- **정합 시험.** `test_deploy_guide.py`와 `test_standalone_env.py` 26개 통과.
- **ruff(린트·포맷), pyright, `check_type_escapes`, import-linter.** 반영 뒤에도 깨끗하다(`ruff check .`, `ruff format --check .`, `pyright` 0건, 계약 2개 유지).
- **예시 명령.** 시험이 풀어 둔 묶음으로 임시 스택을 띄워 쳐 본 결과는 티켓 Comments의 표에 있다. 치지 못한 것은 `sudo mkdir`, 실제 NFS·SMB 공유 폴더, `docker compose restart server worker`다.
- **검사 러너 전체(`tools/run_checks.py`).** pre-commit이 커밋에서 돈다. 결과는 커밋 뒤에 PR 본문에 적는다.

## 셀프 리뷰(`/code-review`, base `bb4a848`, 수정 8·미추적 3·커밋 0)

표준 축은 Major 2, Minor 7, Nit 4를, 명세 축은 Critical·Major 없이 (a) 4, (b) 2, (c) 3을 냈다.

**고친 것**
- Major. `.env.example`의 네 설정(시간대, 보관 기간 둘, 읽기 한도)이 "비우면 기본값"이라고 적었으나, 값을 빈 채로 두면 `load_settings`가 `ConfigurationError`로 기동을 거부했다(네 변수를 하나씩 `RAG_*=""`로 쳐서 확인했다). "적지 않으면"으로 고쳤다. `RAG_ENGINE_SOURCES_DIR`은 compose의 `:-`가 빈 값을 받아 "비우면"이 맞다.
- Major. README의 공유 폴더 측정 문단이 명세의 조건을 뺐다. "읽기를 맡은 별도 스레드만 막힌 컨테이너(서버와 작업자가 쓰는 모양)", "끊고 10초에 멈췄을 때", "읽기가 이미 돌아와 있던 경우도 센 수", `hard` SMB 두 경우를 재지 못한 단서, 서버가 응답만 멈춘 지 200초쯤 뒤에는 강제 종료로도 8초 안에 끝나지 않았다는 반례를 더했다.
- 정합 시험이 `.env.example` 예시 줄 다섯을 모두 잠그게 넓히고, 네 기본값이 `Settings`와 같은지 보게 했다. 변이 다섯을 더했다.
- README: 느린 공유 폴더 절에 작업자 로그 `connector_call_timed_out` 한 줄과 "어느 파일에서 걸렸는지는 기록에 남지 않는다"를 더했다(명세 195행이 안내가 적는다고 한 것). SMB 절에 soft로 붙일 때 치르는 값 둘(미리 열어 둔 파일의 읽기가 돌아오지 않는다, 목록을 받은 뒤 끊기면 동기화가 오래 돈다)을 더했다. 원천 이름 규칙에 "소문자나 숫자로 시작"을, `unchanged`의 뜻(내용이 그대로여서 건드리지 않은 파일 수)을, 숨김 파일 제외가 숨김 폴더 안의 파일까지라는 것을, 겹치는 폴더의 409 `source_folder_overlap`을 더했다. 떼었다 붙인 폴더가 그대로 보인다는 서술에는 잰 환경의 한계(메모리 파일 시스템으로 흉내 냄)를 달았다. 6절에서 "원천 폴더"와 "하위 폴더"를 한 번 정의했다. `ingest` 이관의 삭제 요청은 `curl -G --data-urlencode`로 바꿨다.
- `.env.example`: `RAG_ENGINE_SOURCES_DIR`에 `data/src`처럼 `./`나 `/`로 시작하지 않는 값은 compose가 이름 붙은 볼륨으로 읽어 `undefined volume` 오류로 멈춘다는 주의를 더했다(`docker compose config`로 그 오류를 확인했다).
- compose 머리 주석의 "운영자가 고치는 것"에 `sources/`를 더했다.
- 시험: 쓰는 곳이 없던 `search(stack, query)`의 `query` 인자를 걷었다. 기다리는 상한 두 개(120초, 600초)에 근거 주석을 달았다.

**남긴 것과 이유**
- `sync_record`가 `time.sleep(0.5)`로 폴링하는 것(표준 Nit). 같은 파일의 기존 시험(`until_ready` 등)이 같은 모양이라 맞춰 두었다.
- README 2절에 `sources/` 줄을 더한 것(명세 축 (b)). 요구한 네 군데 밖이지만 폴더 목록이 빠지면 낡아서 두었다.
- Minor. 폴링 루프가 셋인 것은 기존 시험과 같은 모양이라 합치지 않았다.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장)**
- README 느린 공유 폴더 절: "한도를 넘기면 작업자 로그에 `connector_call_timed_out` 한 줄이 남습니다. 어느 파일에서 걸렸는지는 동기화 기록에도 로그에도 남지 않으므로, 가장 큰 파일을 의심하십시오." 코드로 본 것은 `guard.py`가 그 이벤트를 `source`, `kind`, `outstanding`만 실어 낸다는 것이다.
- README: "숨김 파일과 숨김 폴더 안의 파일(경로의 어느 이름이든 `.`으로 시작하는 것)과 오피스 임시 파일(`~$`로 시작하는 파일 이름)은 늘 뺍니다." `ingest_policy._is_default_excluded`를 읽은 것이다.
- README: "원천의 이름은 영문 소문자나 숫자로 시작하고, 영문 소문자와 숫자, `-`, `_`만 쓰며, 63자까지입니다." `SOURCE_NAME_PATTERN`을 읽은 것이다.
- README: "`unchanged`는 내용이 그대로여서 건드리지 않은 파일 수입니다." 임시 스택의 `reread` 기록(`listed` 1, `unchanged` 1)으로 본 것이다.
- `.env.example`: "data/src 처럼 적으면 ... compose 가 undefined volume 오류로 멈춘다." `docker compose config`가 `service "server" refers to undefined volume data/src: invalid compose project`로 끝났다.
- `.env.example`: "적지 않으면 Asia/Seoul·30·90·600." `settings.py`의 기본값과 정합 시험이 같다.

**다시 돌린 것.** 위 검증 절의 정합 시험 26개와 ruff, pyright, 타입 우회, 경계는 반영 뒤 결과다. 단독 compose 시험은 아래에 이어 적는다.

## PR 직전 리뷰(`coderabbit-review`, CodeRabbit CLI 0.7.5, 커밋하지 않은 변경 전체)

CLI가 끝까지 돌았다(`Plan: Free`, 좌석 없음이어도 막히지 않았다). 지적 3건은 모두 `deploy/standalone/README.md`이고 오탐은 없다. CLI는 셋 다 major로 냈으나 문서 문구라 Minor로 내렸고 Critical·Major는 없다. 밀어 둔 주장 다섯은 서브에이전트가 코드를 열어 대 보았고 모두 맞았다(다섯째 `undefined volume`은 이 세션이 `docker compose config`로 이미 확인했다).

**고친 것**
- 명령 `mkdir`, `cp`, `chmod`, `sudo mkdir`이 기본 폴더(`sources/`)만 가정했다. 다른 폴더를 고른 설치가 그대로 치면 설치 폴더에 파일이 생기고 `/sources`에는 붙지 않는다. 명령 앞에 "기본 폴더를 쓴다고 보고 적었으니 `RAG_ENGINE_SOURCES_DIR`로 다른 폴더를 골랐다면 `sources`를 그 폴더로 바꿔 읽으십시오"를 더했다.
- `ingest` 이관 2단계가 `succeeded`만 보고 `default` 문서를 지우라고 했다. 같은 README가 색인은 동기화 뒤에 작업자가 이어 한다고 적었으므로 그 사이에 검색이 빈다. 문서 응답의 `indexes[].status`(`admin_models.py`의 `IndexStatusResponse.status`, 값은 `pending`·`indexed`·`failed`)가 `indexed`인지 본 뒤 지우라고 고쳤다.
- `chmod -R a+rX sources`가 서버 기계의 다른 계정에도 문서를 연다는 것을 적었다. 필요한 사용자는 uid 10001뿐이므로 다른 계정이 있고 문서를 숨겨야 하는 기계는 그룹이나 ACL로 uid 10001에게만 주도록 했다. CLI도 설계 판단에 가깝다고 했으나 위험을 한 문장으로 적는 것이 싸서 고쳤다.

**남긴 것.** 없다.

**다시 돌린 것.** 정합 시험(`tests/tools/test_deploy_guide.py`)은 README 수정 뒤 14개가 통과했다(종료 코드 0, 1.08초. `test_standalone_env.py`는 README를 읽지 않아 다시 돌리지 않았다). 문구만 바꿨고 `compose.yaml`과 코드는 그대로라서 단독 compose 시험의 대상은 바뀌지 않았다.

## 회고

후보 5개를 냈고 판정은 승인 0, 기각 5, 넘김 0이다. 대기열 찾기(`MSYS`, `PATHCONV`, `git.bash`, `bootstrap-token`)는 같은 일을 다룬 항목을 찾지 못했다.

- **훅이 막은 명령(`python3`, `.env`를 Bash로 읽기, 체크아웃 밖으로 `cd`).** 기각. 훅이 그 자리에서 막았고 다른 명령으로 바로 이어 갔다. 사건은 있으나 이미 있는 훅이 그 일을 했다.
- **Git Bash가 명령 인자와 `/tmp`를 바꾼 것(한글 본문 400, `-v /import:ro`, `curl -o /tmp`).** 기각. 이 PC의 셸 탓이고 제품 명령은 그대로 두었다. 같은 실수가 처음이라 대기열에도 잇지 않고 일지에만 적는다. 다음에 같은 모양이 나오면 이 줄이 첫 회차다.
- **`bootstrap-token`이 살아 있는 토큰이 있으면 새로 내지 않아 401이 난 것.** 기각. 도구가 안내 문구로 이미 방법을 알려 준다.
- **`.env.example`의 "비우면 기본값" 오류(빈 값은 `ConfigurationError`).** 기각. 셀프 리뷰가 잡아 이 PR에서 문구를 고치고 정합 시험이 네 기본값을 잠근다. 리뷰가 제 몫을 한 사건이라 회차로 세지 않는다.
- **워크트리 가드가 `git` 복합 명령을 거부한 것.** 기각. 가드가 막았고 명령을 나누어 이어 갔다.

**만료.** 승인 줄의 가장 늦은 날짜가 2026-11-10인 세 항목(`check-quotes-untracked-scope`, `constitution-edit-beyond-approval`, `rules-skipped-on-bash-read`)의 상태를 `만료 2026-11-25`로 고쳤다. 로컬 ref와 `origin/dev`의 두 출력에 모두 든 항목이다.

## 다음

- 이 기능(source-sync)의 마지막 티켓이다. 병합되면 기능 계획의 `**끝:**` 줄이 dev에 들어가므로 출시 PR(dev→main)을 여는 계기가 된다(`next-session` `merge.md`의 "출시 PR"의 계기).
- 같은 PR에서 `deploy/standalone/` 아래를 고쳤으므로 제품 변경이고 다음 릴리스에 실린다. 볼륨 하나를 더하는 변경이라 올릴 때 운영자가 손댈 것이 없고 PR 제목에 느낌표를 붙이지 않는다.
