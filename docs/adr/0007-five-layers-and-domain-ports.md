---
status: accepted
date: 2026-11-09
---

# 층은 main > server·worker > adapters > app > domain 다섯이고, 포트는 domain의 Protocol이며, 이미지는 서버와 작업자 둘이다

킥오프의 층은 `rag_engine.main > rag_engine.server` 둘이었고 나머지는 core 설계 인터뷰가 정하기로 했다. 플러그인 자리 셋(ADR 0003)과 벡터 저장소(ADR 0006)의 교체가 모두 포트 뒤의 어댑터를 바꾸는 일이어야 하므로 포트·어댑터 모양으로 간다. `domain`에는 엔티티(원천, 그룹, 지식베이스, 문서, 조각, 작업)와 포트가 있다. 포트는 `typing.Protocol`이고 Connector, Transform, Parser, Chunker, Embedder, Reranker, VectorIndex, JobQueue, DocumentStore, BlobStore다. `app`에는 유스케이스(수집, 동기화, 검색, 재색인, 삭제, 토큰 발급)가 있고 포트만 부른다. DocumentStore, VectorIndex, JobQueue의 PostgreSQL 어댑터는 한 트랜잭션을 공유할 수 있어야 한다. 문서의 조각 교체(ADR 0006), 색인 판 전환(ADR 0008), 문서 상태와 작업 상태(ADR 0009)가 그것에 기댄다. 유스케이스가 그 경계를 열어 세 포트에 넘기는 모양(작업 단위 포트)은 명세가 정한다. `adapters`에는 PostgreSQL(SQLAlchemy·alembic, ADR 0011), TEI(ADR 0010), 파서 라이브러리, 커넥터, 작업 대기열(ADR 0009), 파일 저장소(ADR 0013)의 구현이 있다. `server`는 FastAPI 앱을, `worker`는 작업자를 조립하고 나란히 서며, `main`의 관리 명령이 둘 중 하나를 띄운다. 경계는 `pyproject.toml`의 import-linter layers 계약이 판정한다. 계약을 `rag_engine.main` > `rag_engine.server | rag_engine.worker` > `rag_engine.adapters` > `rag_engine.app` > `rag_engine.domain`으로 고치는 일은 core의 첫 구현 티켓이 패키지를 만들 때 하고, 그때까지 계약은 킥오프의 둘 그대로다.

프로세스와 이미지는 서버와 작업자 둘이고 같은 파이썬 패키지에서 나온다(`docs/constitution/tech.md`의 한 패키지 원칙). 둘 다 torch가 없다. 임베딩과 리랭커는 별도 컨테이너가 돌리기 때문이다(ADR 0010). 단독 compose의 기본 컨테이너는 서버, 작업자, PostgreSQL, 임베딩 TEI, 리랭커 TEI 다섯이다.

## Considered Options

- 둘 유지(main > server)에 모듈만 나눈다: 플러그인과 어댑터가 서버 모듈에 섞여 import-linter가 교체 경계를 판정하지 못한다.
- 셋(server > service > repository): 플러그인 자리와 외부 서비스(TEI)가 service에 섞이고, 작업자가 설 자리가 없다.
- 이미지 하나에 명령으로 서버·작업자를 가른다: 처음 추천이었으나 이미지 둘이 compose에서 역할과 자원(작업자만 CPU를 많이 씀)을 따로 조절할 수 있어 둘로 간다.

## Consequences

- 테스트는 포트에 가짜를 끼워 app을 데이터베이스 없이 시험하고, adapters는 테스트 PostgreSQL과 TEI 스텁으로 시험한다.
- `CLAUDE.md`의 레이어 절과 `.scratch/plan-head.md`의 목표 배치가 다섯 층으로 바뀐다. `CLAUDE.md`는 면제 파일이 아니라 core의 첫 티켓이 고친다.
- 포트가 열이라 첫 티켓이 커진다. 계약(포트와 인터페이스 판)을 바꾸는 티켓은 기능의 첫 티켓이고 다른 티켓을 막는다(`docs/agents/issue-tracker.md`).
