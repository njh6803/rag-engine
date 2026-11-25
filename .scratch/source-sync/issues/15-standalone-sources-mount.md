# 15: 단독 compose와 설치 안내

**What to build:** 단독 compose로 설치한 운영자가 `.env`에 서버 기계의 폴더 하나(`RAG_ENGINE_SOURCES_DIR`, 적지 않으면 설치 폴더의 `sources/`)를 적으면, 그 폴더가 서버와 작업자 컨테이너의 `/sources`에 읽기 전용으로 붙는다. 원천을 더할 때 compose 파일을 고치지 않는다. 설치 안내가 원천 폴더를 만들고 권한을 맞추는 법, 공유 폴더를 붙이는 때와 다시 띄우는 명령, 원천을 만들어 동기화하는 예시 명령, 동기화가 문서를 지우지 않는 경우와 그때의 길, 끊긴 공유 폴더 때문에 동기화가 계속 실패할 때 할 일의 차례를 적는다. 이 기능의 마지막 티켓이다(스토리 5, 41).

**Blocked by:** 14 (정리 작업)

**Status:** done

- [x] 명세 "티켓을 나눌 때 함께 둘 것"대로 단독 compose에 부모 폴더를 붙이는 변경, `.env.example`, 설치 안내, 단독 compose 시험을 이 티켓에 함께 둔다.
- [x] 단독 compose(`deploy/standalone/compose.yaml`)가 서버와 작업자 두 서비스에 `.env`의 `RAG_ENGINE_SOURCES_DIR`(적지 않으면 설치 폴더의 `sources/`)를 `/sources`로 읽기 전용으로 붙이고, 마이그레이션 컨테이너에는 붙이지 않는다. 전파 설정은 넣지 않는다(명세 "단독 compose와 설치 안내", 사용자 선택). compose가 정하는 서버 설정에 `RAG_SOURCES_DIR`(`/sources`)를 더해 `.env`가 덮어쓰지 못하게 한다.
- [x] 배포 파일 묶음에 `sources/README.txt`를 넣는다. 이 폴더 아래에 원천마다 하위 폴더를 만든다는 것을 두세 줄로 적는다(부모 폴더 바로 아래의 파일이라 어느 원천에도 들지 않는다).
- [x] `deploy/standalone/.env.example`에 주석 처리한 예시 줄 다섯을 더한다. `RAG_ENGINE_SOURCES_DIR`, `RAG_SCHEDULE_TIMEZONE`, `RAG_DELETED_RETENTION_DAYS`, `RAG_SYNC_RECORD_RETENTION_DAYS`, `RAG_SOURCE_READ_TIMEOUT_SECONDS`다.
- [x] 설치 안내(`deploy/standalone/README.md`)의 네 군데를 고친다(명세 "단독 compose와 설치 안내"). 6절 "문서 넣기"에 하위 절 "서버 폴더의 문서 가져오기"를 더하고, 3절이 compose가 정하는 값으로 적은 셋을 넷으로 고치고, 11절 "볼륨과 지우면 안 되는 것"에 `sources/`는 이 서버가 읽기만 하고 쓰거나 지우지 않는다는 것을 적고, 14절 "업그레이드"가 그대로 두는 것으로 적은 목록에 `sources/`를 더한다. 새 절을 끼워 넣지 않으므로 다른 절을 번호로 가리킨 자리(9절, 10절, 12절, 14절)가 그대로다.
- [x] 6절의 새 하위 절은 명세 "단독 compose와 설치 안내"가 적을 것으로 든 것을 모두 적는다. 그 가운데 사용자가 고른 둘은 명세의 문장대로다. 끊긴 공유 폴더 때문에 원천이 계속 `source_unreadable`일 때의 차례 셋(공유 폴더를 되살린다, 그래도 그대로면 `docker compose restart server worker`로 둘을 함께 다시 띄운다, 그 명령이 컨테이너를 멈추지 못했다는 오류로 실패하면 공유 폴더를 되살린 뒤 다시 치거나 서버 기계를 다시 띄운다)과 함께 적는 셋, 그리고 SMB 공유 폴더를 `hard` 옵션 없이 기본값으로 붙이라는 것이다. 이 기능이 없던 묶음에서 올라온 설치에서는 Docker가 `sources/`를 root의 폴더로 만들어 두어 그 아래에 원천 폴더를 만들 때 관리자 권한이 필요하다는 것, `ingest` 명령으로 `default`에 넣어 둔 폴더를 서버 경로 원천으로 옮기는 절차(명세 "따르는 것과 범위"), 끝나지 않는 동기화를 멈추는 차례(원천을 지우고 그 동기화의 기록이 `source_deleted`로 닫힌 것을 본 뒤에 되살린다)도 적는다. 예시 명령은 실제로 쳐 본 결과를 티켓 Comments에 남긴다.
- [x] 설치 안내와 배포 파일 묶음의 정합을 보는 저장소 상태 시험(`tests/tools/test_deploy_guide.py`, `tests/tools/test_standalone_env.py`)이 새 변수와 새 파일에도 맞게 초록이다. 정합을 잠글 자리(안내가 적은 변수 이름과 compose의 값, `sources/README.txt`)가 생기면 그 시험을 넓힌다.
- [x] 단독 compose 시험(`tests/standalone/test_standalone_compose.py`)에 장면 하나를 더한다(명세 "Testing Decisions"). 설치 폴더의 `sources/` 아래에 폴더와 파일을 두고 띄운 뒤 원천을 만들어 지금 동기화하면 그 문서가 검색에 나오고, 서버와 작업자 컨테이너가 `/sources`에 쓰지 못한다. 지금의 단독 compose 시험과 같은 조건에서 돈다.
- [x] 이 티켓의 PR 제목에는 느낌표를 붙이지 않는다. 볼륨 하나를 더하는 변경은 올릴 때 운영자가 손댈 것이 없다(명세 "단독 compose와 설치 안내"의 업그레이드 항목, 프로브 `mount-propagation/probe_out.txt`의 10, ADR 0020).
- [x] 이 기능의 마지막 티켓을 닫는 커밋이 기능 계획(`.scratch/source-sync/plan.md`)에 `**끝:**` 줄을 적고, 기능 단락(`docs/release-notes/features/source-sync.md`, 한 단락에 줄바꿈을 뺀 400자 이하)을 싣는다(`docs/agents/issue-tracker.md`, `CLAUDE.md` 지도). 계획 표는 `uv run python tools/plan_table.py`로 다시 만든다.
- [x] 검사 넷이 초록이다. 원칙 II는 `tools/check_type_escapes.py`가 판정한다.

## Comments

**2026-11-25, 구현 세션(Sonnet 5.5). 예시 명령을 실제로 쳐 본 결과.**

단독 compose 시험(`uv run pytest tests/standalone -q`, 26개)이 새 장면까지 통과했다(12분 13초, 이 PC의 Docker Desktop). 새 장면은 `sources/regulations/leave.pdf`를 두고 띄워 원천을 만들고 지금 동기화하면(기록 `succeeded`, 받은 1, 더한 1) 그 문서가 MCP 검색에 나오고, 서버와 작업자의 `/sources`가 읽기 전용이라 쓰기가 `EROFS`로 막히며, 마이그레이션 컨테이너에는 `/sources`가 없는 것을 본다. 설치 안내와 묶음의 정합 시험(`tests/tools/test_deploy_guide.py`, `tests/tools/test_standalone_env.py`) 26개도 통과했다.

설치 안내 6절의 명령은 시험이 풀어 둔 묶음(`rag-engine-0.1.0-rc.1`, 모델 포함)으로 스택을 다시 띄워 `curl -k https://localhost/...`로 쳐 보았다. 임시 스택은 쳐 본 뒤 `down -v`로 내렸다.

| 안내의 명령 | 친 결과 |
|---|---|
| `POST /api/v1/admin/sources` (본문은 안내의 것) | 201. `schedule`을 적으면 `next_run_at`이 `.env` 시간대의 02:00(UTC 17:00)으로 나온다 |
| `POST .../regulations/check` | 200 `{"ok":true,"code":null}` |
| `POST .../regulations/sync` | 202, `sync_record_id`와 `job_id` |
| `GET .../regulations/sync-records` | `succeeded`, `listed` 1, `added` 1. 이어서 `GET /api/v1/admin/documents?source=regulations`의 색인 상태가 `indexed` |
| `PATCH .../regulations` (`schedule`과 `exclude_patterns`) | 200. 처음에는 400 `There was an error parsing the body`였는데, 한글이 든 `-d` 문자열을 Windows의 Git Bash가 UTF-8로 넘기지 못한 탓이다. 같은 본문을 UTF-8 파일로 `--data-binary @파일`로 보내면 200이다 |
| 문서가 있는 원천에서 폴더를 비우고 동기화 | `failed`, `source_unreadable`, `listed` 0 |
| 같은 원천에 `.txt`만 둔 폴더 | `failed`, `nothing_accepted`, `not_accepted` `unsupported_type` 1 |
| 위 상태에서 `{"apply_empty":true}` | `succeeded`, `deleted` 1, 문서 상태가 `deleted` |
| 폴더가 사라졌을 때 동기화, `apply_empty` 동기화 | 둘 다 `failed`, `source_unreadable`(`listed`는 없음) |
| 폴더가 사라졌던 원천의 같은 자리에 빈 폴더를 만들고 `{"apply_empty":true}` | `succeeded`, `deleted` 1 |
| `{"reread":true}` | 202, 기록의 `options`에 `reread`가 남고 `unchanged` 1 |
| `DELETE .../regulations` | 202, `job_id` |
| `POST .../regulations/restore` | 202, `connection_check` `ok` 참. 문서 목록에 `leave.pdf`가 `indexed`로 돌아왔다 |
| `ingest`로 `default`에 넣은 문서의 목록과 `DELETE /api/v1/ingest/documents?key=leave.pdf` | 목록에 키 `leave.pdf`, 삭제는 204, 그 뒤 목록의 상태가 `deleted` |

쳐 보고 안내를 고친 곳은 하나다. 처음 안내는 빈 폴더 동기화가 늘 실패한다고 적었으나, 문서가 아직 없는 원천은 지울 문서가 없어 `succeeded`(`listed` 0)로 끝났다(`_guard_empty_list`가 그 원천에 지워지지 않은 문서가 있을 때만 막는다). 안내에 "그 원천에 문서가 이미 있는데"를 더하고 문서가 없는 원천은 성공으로 끝난다고 적었다.

치지 못한 것. `sudo mkdir -p sources/regulations`(root 폴더로 만들어진 `sources/`)와 공유 폴더(SMB, NFS)를 붙이는 명령, `docker compose restart server worker`는 이 PC에서 치지 않았다. 앞의 둘은 리눅스 호스트의 폴더 소유와 공유 폴더가 필요하고, 마지막은 안내가 "붙인 뒤 다시 띄운다"는 차례만 적는다. 공유 폴더의 동작과 `hard` 옵션에 관한 문장은 명세와 프로브 `.scratch/source-sync/probes/stuck-mount/`의 것을 옮긴 것이고, 안내가 재지 않았다고 밝힌 부분은 그대로 밝혔다.

티켓 04의 일지가 15에 넘긴 물음("단독 compose가 `RAG_MAX_UPLOAD_MB`를 컨테이너의 환경 변수로 넘기는지")은 compose의 설정 풀이로 확인했다. `env_file`을 임시 파일로 바꾼 사본에 `RAG_MAX_UPLOAD_MB=250`을 적고 `docker compose --env-file <그 파일> config --format json`을 치자 서버, 작업자, 마이그레이션의 `environment`에 모두 `250`이 실렸다. 서버 경로 커넥터가 읽는 값이 `.env`에서 그대로 컨테이너에 닿는다는 뜻이다. 실제 `.env`로 스택을 띄워 확인한 것은 아니다(`.env`를 쓰는 명령은 이 세션의 훅이 막았다).

셀프 리뷰가 안내를 고친 곳은 위 하나 말고도 있다. `.env.example`의 네 설정(시간대, 보관 기간 둘, 읽기 한도)에 적었던 "비우면 기본값"은 틀렸다. 값을 빈 채로 두면 `load_settings`가 `ConfigurationError`로 기동을 거부했다(네 변수를 하나씩 `RAG_*=""`로 쳐서 확인했다). 그래서 "적지 않으면"으로 고쳤고, 정합 시험이 네 예시 값이 `Settings`의 기본값과 같은지도 본다. `ingest` 이관의 삭제 요청 예시는 한글과 공백이 든 키를 위해 `curl -G --data-urlencode "key=…"`로 바꿨다. 요청 줄이 `?key=%ed%95%9c…`로 인코딩되는 것은 로컬 임시 서버로 보았고, 실제 서버에 한글 키로 친 것은 아니다.
