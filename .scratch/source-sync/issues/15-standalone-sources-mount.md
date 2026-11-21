# 15: 단독 compose와 설치 안내

**What to build:** 단독 compose로 설치한 운영자가 `.env`에 서버 기계의 폴더 하나(`RAG_ENGINE_SOURCES_DIR`, 적지 않으면 설치 폴더의 `sources/`)를 적으면, 그 폴더가 서버와 작업자 컨테이너의 `/sources`에 읽기 전용으로 붙는다. 원천을 더할 때 compose 파일을 고치지 않는다. 설치 안내가 원천 폴더를 만들고 권한을 맞추는 법, 공유 폴더를 붙이는 때와 다시 띄우는 명령, 원천을 만들어 동기화하는 예시 명령, 동기화가 문서를 지우지 않는 경우와 그때의 길, 끊긴 공유 폴더 때문에 동기화가 계속 실패할 때 할 일의 차례를 적는다. 이 기능의 마지막 티켓이다(스토리 5, 41).

**Blocked by:** 14 (정리 작업)

**Status:** ready-for-agent

- [ ] 명세 "티켓을 나눌 때 함께 둘 것"대로 단독 compose에 부모 폴더를 붙이는 변경, `.env.example`, 설치 안내, 단독 compose 시험을 이 티켓에 함께 둔다.
- [ ] 단독 compose(`deploy/standalone/compose.yaml`)가 서버와 작업자 두 서비스에 `.env`의 `RAG_ENGINE_SOURCES_DIR`(적지 않으면 설치 폴더의 `sources/`)를 `/sources`로 읽기 전용으로 붙이고, 마이그레이션 컨테이너에는 붙이지 않는다. 전파 설정은 넣지 않는다(명세 "단독 compose와 설치 안내", 사용자 선택). compose가 정하는 서버 설정에 `RAG_SOURCES_DIR`(`/sources`)를 더해 `.env`가 덮어쓰지 못하게 한다.
- [ ] 배포 파일 묶음에 `sources/README.txt`를 넣는다. 이 폴더 아래에 원천마다 하위 폴더를 만든다는 것을 두세 줄로 적는다(부모 폴더 바로 아래의 파일이라 어느 원천에도 들지 않는다).
- [ ] `deploy/standalone/.env.example`에 주석 처리한 예시 줄 다섯을 더한다. `RAG_ENGINE_SOURCES_DIR`, `RAG_SCHEDULE_TIMEZONE`, `RAG_DELETED_RETENTION_DAYS`, `RAG_SYNC_RECORD_RETENTION_DAYS`, `RAG_SOURCE_READ_TIMEOUT_SECONDS`다.
- [ ] 설치 안내(`deploy/standalone/README.md`)의 네 군데를 고친다(명세 "단독 compose와 설치 안내"). 6절 "문서 넣기"에 하위 절 "서버 폴더의 문서 가져오기"를 더하고, 3절이 compose가 정하는 값으로 적은 셋을 넷으로 고치고, 11절 "볼륨과 지우면 안 되는 것"에 `sources/`는 이 서버가 읽기만 하고 쓰거나 지우지 않는다는 것을 적고, 14절 "업그레이드"가 그대로 두는 것으로 적은 목록에 `sources/`를 더한다. 새 절을 끼워 넣지 않으므로 다른 절을 번호로 가리킨 자리(9절, 10절, 12절, 14절)가 그대로다.
- [ ] 6절의 새 하위 절은 명세 "단독 compose와 설치 안내"가 적을 것으로 든 것을 모두 적는다. 그 가운데 사용자가 고른 둘은 명세의 문장대로다. 끊긴 공유 폴더 때문에 원천이 계속 `source_unreadable`일 때의 차례 셋(공유 폴더를 되살린다, 그래도 그대로면 `docker compose restart server worker`로 둘을 함께 다시 띄운다, 그 명령이 컨테이너를 멈추지 못했다는 오류로 실패하면 공유 폴더를 되살린 뒤 다시 치거나 서버 기계를 다시 띄운다)과 함께 적는 셋, 그리고 SMB 공유 폴더를 `hard` 옵션 없이 기본값으로 붙이라는 것이다. 이 기능이 없던 묶음에서 올라온 설치에서는 Docker가 `sources/`를 root의 폴더로 만들어 두어 그 아래에 원천 폴더를 만들 때 관리자 권한이 필요하다는 것, `ingest` 명령으로 `default`에 넣어 둔 폴더를 서버 경로 원천으로 옮기는 절차(명세 "따르는 것과 범위"), 끝나지 않는 동기화를 멈추는 차례(원천을 지우고 그 동기화의 기록이 `source_deleted`로 닫힌 것을 본 뒤에 되살린다)도 적는다. 예시 명령은 실제로 쳐 본 결과를 티켓 Comments에 남긴다.
- [ ] 설치 안내와 배포 파일 묶음의 정합을 보는 저장소 상태 시험(`tests/tools/test_deploy_guide.py`, `tests/tools/test_standalone_env.py`)이 새 변수와 새 파일에도 맞게 초록이다. 정합을 잠글 자리(안내가 적은 변수 이름과 compose의 값, `sources/README.txt`)가 생기면 그 시험을 넓힌다.
- [ ] 단독 compose 시험(`tests/standalone/test_standalone_compose.py`)에 장면 하나를 더한다(명세 "Testing Decisions"). 설치 폴더의 `sources/` 아래에 폴더와 파일을 두고 띄운 뒤 원천을 만들어 지금 동기화하면 그 문서가 검색에 나오고, 서버와 작업자 컨테이너가 `/sources`에 쓰지 못한다. 지금의 단독 compose 시험과 같은 조건에서 돈다.
- [ ] 이 티켓의 PR 제목에는 느낌표를 붙이지 않는다. 볼륨 하나를 더하는 변경은 올릴 때 운영자가 손댈 것이 없다(명세 "단독 compose와 설치 안내"의 업그레이드 항목, 프로브 `mount-propagation/probe_out.txt`의 10, ADR 0020).
- [ ] 이 기능의 마지막 티켓을 닫는 커밋이 기능 계획(`.scratch/source-sync/plan.md`)에 `**끝:**` 줄을 적고, 기능 단락(`docs/release-notes/features/source-sync.md`, 한 단락에 줄바꿈을 뺀 400자 이하)을 싣는다(`docs/agents/issue-tracker.md`, `CLAUDE.md` 지도). 계획 표는 `uv run python tools/plan_table.py`로 다시 만든다.
- [ ] 검사 넷이 초록이다. 원칙 II는 `tools/check_type_escapes.py`가 판정한다.
