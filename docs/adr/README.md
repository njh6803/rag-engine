# ADR 색인

번호열은 하나다. 지역 결정도 여기 넣고 제목에 범위를 적는다. 형식은 domain-modeling 스킬의 ADR-FORMAT(짧게, 결정과 이유). 새 ADR을 쓰면 이 표에 한 줄 더한다.

| 번호 | 제목 | 상태 | 날짜 |
|---|---|---|---|
| [0001](0001-mcp-opens-read-tools-only.md) | MCP로는 읽기 도구만 열고, 쓰기는 관리 API와 수집 API로 나눈다 | accepted | 2026-11-09 |
| [0002](0002-own-postgresql-by-one-connection-string.md) | 이 서버는 자기 PostgreSQL 데이터베이스를 쓰고 연결 문자열 하나만 받는다 | accepted | 2026-11-09 |
| [0003](0003-three-plugin-slots-and-private-transforms.md) | 수집 파이프라인에 플러그인 자리 셋을 두고, 설치처별 변환 플러그인은 설치처의 비공개 저장소에 둔다 | accepted | 2026-11-09 |
| [0004](0004-keep-latency-not-questions.md) | 검색 질문의 내용을 남기지 않고 지연 시간만 남긴다 | accepted | 2026-11-09 |
| [0005](0005-rest-and-mcp-in-one-fastapi-app.md) | REST와 MCP는 한 FastAPI 앱이 열고, MCP는 공식 SDK 2.x의 Streamable HTTP를 `/mcp`에 붙인다 | accepted | 2026-11-09 |
| [0006](0006-pgvector-and-postgres-fts-with-kiwi.md) | 벡터 저장소는 pgvector와 PostgreSQL 전문 검색으로 하고, 한국어 형태소는 앱의 Kiwi가 맡는다 | accepted | 2026-11-09 |
| [0007](0007-five-layers-and-domain-ports.md) | 층은 main > server·worker > adapters > app > domain 다섯이고, 포트는 domain의 Protocol이며, 이미지는 서버와 작업자 둘이다 | accepted | 2026-11-09 |
| [0008](0008-groups-knowledge-bases-identity-and-index-version.md) | 문서는 그룹에 속하고 지식베이스는 그룹 집합 위의 색인이다. 문서는 (원천, 키)로 식별하고, 지식베이스마다 색인 판을 두며, 교체는 문서 단위와 지식베이스 판 전환이다 | accepted | 2026-11-09 |
| [0009](0009-job-queue-in-postgresql.md) | 작업 대기열은 PostgreSQL 작업 표로 직접 구현한다(SKIP LOCKED + LISTEN/NOTIFY) | accepted | 2026-11-09 |
| [0010](0010-embedding-and-reranker-as-tei-containers.md) | 임베딩과 리랭커는 설치 안의 TEI 컨테이너가 돌리고, 서버는 `/v1/embeddings`·`/tokenize`·`/rerank` 셋으로 부른다. 청킹 전략은 포트 뒤의 저장소 안 집합이다 | accepted | 2026-11-09 |
| [0011](0011-sqlalchemy-core-async-and-alembic.md) | 데이터 접근은 SQLAlchemy 2.1 Core 비동기(psycopg 3)로 하고, 마이그레이션은 alembic이 한다 | accepted | 2026-11-09 |
| [0012](0012-plugin-interface-versions-and-pull-connectors.md) | 플러그인 인터페이스는 Protocol과 `interface_version`과 entry points로 열고, 커넥터는 열거와 받기로 동작한다 | accepted | 2026-11-09 |
| [0013](0013-soft-delete-archive-table-and-blob-store.md) | 삭제는 소프트 삭제 뒤 보관 기간이 지나면 물리 삭제하고, 원본은 파일 저장소 포트 뒤의 볼륨에 둔다 | accepted | 2026-11-09 |
| [0014](0014-tokens-in-database-and-required-allowed-hosts.md) | 인증 토큰은 데이터베이스에 두고 관리 API로 발급·회수하며, MCP 허용 호스트 설정은 필수다 | accepted | 2026-11-09 |
| [0015](0015-common-conventions.md) | 공통 규약: UUIDv7 식별자, RFC 9457 에러 봉투, UTC 시각, REST 경로 접두, pydantic-settings, JSON Lines 로그, 계약의 `format_version` | accepted | 2026-11-09 |
