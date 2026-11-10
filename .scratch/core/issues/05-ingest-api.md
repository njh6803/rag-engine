# 05: 수집 API의 첫 길

**What to build:** 문서 담당자나 다른 시스템이 `POST /api/v1/ingest/documents`로 파일을 밀어 넣으면 원본이 저장되고 작업이 작업 대기열에 들어가 202와 작업 ID를 받는다. 같은 키에 같은 내용이면 건너뛰고, 내용이 바뀌면 갱신이며, 아직 꺼내지지 않은 작업이 있으면 그 작업을 다시 쓴다.

**Blocked by:** 04 (앱 조립과 인증)

**Status:** ready-for-agent

**03이 넘긴 것:** `adapters/postgres/unit_of_work.py`의 `PostgresTransaction.documents`와 `jobs`는 `NotImplementedError`를 올리는 자리다. 이 티켓이 어댑터로 바꾸고 `tests/adapters/test_unit_of_work.py`를 넓힌다. `PostgresVectorIndex`는 `create_version_index`만 구현했고 나머지 다섯(`replace_chunks`, `delete_chunks`, `archive_chunks`, `get_state`, `save_state`)은 `NotImplementedError`다. 색인 상태(`get_state`, `save_state`)는 수집이 `pending`을 쓰는 이 티켓이 처음 부르면 이 티켓이 구현하고, `replace_chunks`는 07, `delete_chunks`는 그룹을 바꾸는 수집(10)과 삭제(11), `archive_chunks`는 삭제(11)가 처음 부를 때 구현한다. `Catalog` 포트에 03이 더한 메서드 가운데 `add_source`, `add_group`, `add_knowledge_base`, `add_group_to_knowledge_base`는 "같은 이름이 이미 있으면 아무것도 하지 않는" 멱등 쓰기이고, `update_knowledge_base`와 `update_index_version_endpoint`는 덮어쓰는 쓰기다. 시험의 설정 객체는 `tests/conftest.py`의 `make_settings`, 기본 레코드가 든 복제 데이터베이스는 `seeded_database_url` 픽스처다.

- [ ] multipart 칸(`file`, `key`, `group`, `metadata`, `updated_at`)과 제목 규칙, 원천 `default`(명세 "수집 API" 절). `admin` 토큰이 필요하다.
- [ ] 형식 판정(확장자를 먼저, 아니면 바이트 머리)과 415 `unsupported_media_type`, 413 `upload_too_large`, 404 `group_not_found`. 셋 다 작업을 만들지 않는다.
- [ ] `action` `created`, 내용이 바뀐 `updated`, 같은 내용의 `unchanged`(메타데이터·갱신일만 바뀌면 문서 행과 조각의 복사 칸을 같은 트랜잭션에서 고친다)와 상태 코드·`job_id`. 그룹 변경과 `requeued`는 10, `restored`는 11이다.
- [ ] 원본은 작업 단위 전에 `RAG_DATA_DIR/blobs/<문서 UUID>/<원본 UUID>`로 쓴다(`BlobStore` 로컬 어댑터, ADR 0013 이력). 롤백이면 새 원본을 지우고, 커밋 뒤에 옛 원본과 문서 행이 가리키지 않는 새 원본을 지운다(최선 노력. 명세 "수집 파이프라인과 작업" 절).
- [ ] 작업 단위가 잠금 순서(문서 행 `FOR NO KEY UPDATE`, 문서가 드는 지식베이스 행 `FOR SHARE`, 작업 행)를 지키고, 응답이 `unchanged`가 아니면 세대를 하나 올린다. 이 잠금 순서는 뒤 티켓(07, 11, 12, 14)이 같은 자리에서 쓴다. 작업 단위에 `documents`·`jobs` 속성을 더하고, 03의 어댑터 시험(속성이 한 트랜잭션에 든다)을 네 속성으로 넓힌다.
- [ ] 작업을 넣을 때 같은 문서의 대기 작업이 있으면 `INSERT … ON CONFLICT … DO UPDATE` 한 문장으로 그 행을 다시 쓴다(`run_after`를 지금으로, 요청 ID를 이번 것으로, 시도 횟수는 그대로). 작업 행은 요청 ID를 들고, 커밋 시점에 `NOTIFY rag_jobs`가 간다.
- [ ] 같은 키를 동시에 넣는 두 요청은 유일 제약으로 직렬화되고, 진 쪽은 원본을 이긴 문서의 UUID 아래로 옮긴 뒤 갱신으로 처리한다.
- [ ] 시험: 스토리 1, 2(내용 갱신), 3, 11, 40, 415 `unsupported_media_type`와 404 `group_not_found`(둘 다 작업이 생기지 않음), `unchanged` 뒤에 새 원본이 남지 않음. 같은 키를 두 번 넣으면 둘째 응답의 `job_id`가 첫째와 같음(HTTP 시험)과 둘째 대기 작업이 생기지 않음(어댑터 시험. 프로브 `.scratch/core/probes/pg-ddl/ddl_locks.py`의 F가 부분 유일 색인의 `UniqueViolation`을 봤다).
- [ ] 검사 넷이 초록이다.
