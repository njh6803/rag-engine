---
status: accepted
date: 2026-11-09
---

# 층은 main > server·worker > adapters > app > domain 다섯이고, 포트는 domain의 Protocol이며, 이미지는 서버와 작업자 둘이다

킥오프의 층은 `rag_engine.main > rag_engine.server` 둘이었고 나머지는 core 설계 인터뷰가 정하기로 했다. 플러그인 자리 셋(ADR 0003)과 벡터 저장소(ADR 0006)의 교체가 모두 포트 뒤의 어댑터를 바꾸는 일이어야 하므로 포트·어댑터 모양으로 간다. `domain`에는 엔티티(원천, 그룹, 지식베이스, 문서, 조각, 작업)와 포트가 있다. 포트는 `typing.Protocol`이고 Connector, Transform, Parser, Chunker, Embedder, Reranker, VectorIndex, JobQueue, DocumentStore, BlobStore다(바뀜: 이력 2026-11-10 "포트 열에 작업 단위 포트 `UnitOfWork`를 더하고, 포트마다 교체 경계인지 테스트 가짜 자리인지를 밝힌다")(바뀜: 이력 2026-11-10 "포트 열에 `Catalog`와 `TokenStore`를 더한다"). `app`에는 유스케이스(수집, 동기화, 검색, 재색인, 삭제, 토큰 발급)가 있고 포트만 부른다. DocumentStore, VectorIndex, JobQueue의 PostgreSQL 어댑터는 한 트랜잭션을 공유할 수 있어야 한다. 문서의 조각 교체(ADR 0006), 색인 판 전환(ADR 0008), 문서 상태와 작업 상태(ADR 0009)가 그것에 기댄다. 유스케이스가 그 경계를 열어 세 포트에 넘기는 모양(작업 단위 포트)은 명세가 정한다(바뀜: 이력 2026-11-10 "포트 열에 `Catalog`와 `TokenStore`를 더한다"). `adapters`에는 PostgreSQL(SQLAlchemy·alembic, ADR 0011), TEI(ADR 0010), 파서 라이브러리, 커넥터, 작업 대기열(ADR 0009), 파일 저장소(ADR 0013)의 구현이 있다. `server`는 FastAPI 앱을, `worker`는 작업자를 조립하고 나란히 서며, `main`의 관리 명령이 둘 중 하나를 띄운다. 경계는 `pyproject.toml`의 import-linter layers 계약이 판정한다. 계약을 `rag_engine.main` > `rag_engine.server | rag_engine.worker` > `rag_engine.adapters` > `rag_engine.app` > `rag_engine.domain`으로 고치는 일은 core의 첫 구현 티켓이 패키지를 만들 때 하고, 그때까지 계약은 킥오프의 둘 그대로다.

프로세스와 이미지는 서버와 작업자 둘이고 같은 파이썬 패키지에서 나온다(`docs/constitution/tech.md`의 한 패키지 원칙). 둘 다 torch가 없다. 임베딩과 리랭커는 별도 컨테이너가 돌리기 때문이다(ADR 0010). 단독 compose의 기본 컨테이너는 서버, 작업자, PostgreSQL, 임베딩 TEI, 리랭커 TEI 다섯이다.

## Considered Options

- 둘 유지(main > server)에 모듈만 나눈다: 플러그인과 어댑터가 서버 모듈에 섞여 import-linter가 교체 경계를 판정하지 못한다.
- 셋(server > service > repository): 플러그인 자리와 외부 서비스(TEI)가 service에 섞이고, 작업자가 설 자리가 없다.
- 이미지 하나에 명령으로 서버·작업자를 가른다: 처음 추천이었으나 이미지 둘이 compose에서 역할과 자원(작업자만 CPU를 많이 씀)을 따로 조절할 수 있어 둘로 간다.

## Consequences

- 테스트는 포트에 가짜를 끼워 app을 데이터베이스 없이 시험하고, adapters는 테스트 PostgreSQL과 TEI 스텁으로 시험한다(바뀜: 이력 2026-11-10 "포트 열에 작업 단위 포트 `UnitOfWork`를 더하고, 포트마다 교체 경계인지 테스트 가짜 자리인지를 밝힌다").
- `CLAUDE.md`의 레이어 절과 `.scratch/plan-head.md`의 목표 배치가 다섯 층으로 바뀐다. `CLAUDE.md`는 면제 파일이 아니라 core의 첫 티켓이 고친다(바뀜: 이력 2026-11-10 "계약 티켓은 core 02이고 core 01(테스트 DB 러너)이 그 앞에 선다").
- 포트가 열이라 첫 티켓이 커진다(바뀜: 이력 2026-11-10 "포트 열에 작업 단위 포트 `UnitOfWork`를 더하고, 포트마다 교체 경계인지 테스트 가짜 자리인지를 밝힌다")(바뀜: 이력 2026-11-10 "포트 열에 `Catalog`와 `TokenStore`를 더한다"). 계약(포트와 인터페이스 판)을 바꾸는 티켓은 기능의 첫 티켓이고 다른 티켓을 막는다(`docs/agents/issue-tracker.md`)(바뀜: 이력 2026-11-10 "계약 티켓은 core 02이고 core 01(테스트 DB 러너)이 그 앞에 선다").

## 이력

### 2026-11-10 포트 열에 작업 단위 포트 `UnitOfWork`를 더하고, 포트마다 교체 경계인지 테스트 가짜 자리인지를 밝힌다

명세(`.scratch/core/spec.md`)가 정했다. 본문의 포트 열 목록에 열한째 `UnitOfWork`가 든다. 유스케이스가 작업 단위를 열면 그 안에서 DocumentStore, VectorIndex, JobQueue를 얻고, 셋은 한 연결의 한 트랜잭션을 공유하며, 예외 없이 나가면 커밋이고 예외면 롤백이다. 대기열의 "작업"과 다른 말이라 산문에서는 "작업 단위"라 쓰고 코드 식별자는 `UnitOfWork`다. PR #2 둘째 회차의 claude-review가 짚은 Chunker·Embedder·Reranker의 몫은 명세의 Implementation Decisions(포트의 값)에 포트마다 적었다. Embedder와 Reranker는 외부 서비스의 경계(다른 임베딩 서버 어댑터의 자리, ADR 0010 Consequences)이자 app 시험의 가짜 자리이고, Chunker는 지식베이스 설정의 전략 이름으로 고르는 전략 자리이며 교체 경계도 가짜 자리도 아니다. Consequences의 "테스트는 포트에 가짜를 끼워 app을 데이터베이스 없이 시험하고"는 범위가 좁아진다. 주 이음매는 HTTP 표면(REST는 httpx, MCP는 공식 SDK 클라이언트)이고 뒤에는 Docker의 실제 테스트 PostgreSQL과 TEI 스텁을 붙이며, 가짜 포트로 app을 시험하는 것은 실제 데이터베이스로 재현하기 어려운 동시성 교차와 실패 분류뿐이다. 이음매는 사용자가 2026-11-10 명세 세션에서 골랐다(명세의 Testing Decisions).

### 2026-11-10 포트 열에 `Catalog`와 `TokenStore`를 더한다

명세(`.scratch/core/spec.md`)가 정했다. PR #3 봇 5회차의 claude-review가 원천·그룹·지식베이스·색인 판 표와 토큰 표를 맡는 포트가 본문의 열에도 명세에도 없다고 짚었다. 판 전환과 재색인 시작, `migrate`의 기본 레코드, 토큰 발급·회수와 인증이 그 표를 읽고 쓴다. 본문의 포트 열 목록에 열두째 `Catalog`와 열셋째 `TokenStore`가 든다. `Catalog`는 원천, 그룹, 지식베이스(지식베이스와 그룹의 다대다를 포함), 색인 판 레코드를 맡고 작업 단위 안에서 얻는다. 지식베이스 행의 잠금과 판 전환이 문서 상태·색인 상태와 한 트랜잭션에 들어야 하기 때문이다. 그래서 한 트랜잭션을 공유하는 포트는 Catalog, DocumentStore, VectorIndex, JobQueue 넷이다. 판마다의 HNSW 부분 색인과 조각은 VectorIndex의 몫으로 남는다. `TokenStore`는 토큰을 맡고 작업 단위 밖에서 부른다(다른 표와 한 트랜잭션에 들 일이 없다). 둘 다 PostgreSQL 어댑터 하나다. 기존 포트(DocumentStore, VectorIndex)의 몫을 넓히는 안은 이름이 맡는 일보다 좁게 읽히고, Catalog 하나가 토큰까지 맡는 안은 인증 표가 문서 설정과 섞여 고르지 않았다. 사용자가 2026-11-10 명세 세션(PR #3 봇 5회차)에서 골랐다.

### 2026-11-10 계약 티켓은 core 02이고 core 01(테스트 DB 러너)이 그 앞에 선다

core 티켓을 쪼개면서 검사 러너가 테스트 PostgreSQL을 띄우는 변경이 core 01이 되었다(`.scratch/core/issues/01-test-db-runner.md`, `.scratch/plan-head.md`). 그래서 Consequences의 "core의 첫 티켓"은 계약 티켓인 core 02(`.scratch/core/issues/02-contract-layers-ports-schema.md`)를 가리키고, "기능의 첫 티켓"은 "계약 티켓"으로 읽는다. 계약 티켓이 다른 모든 core 티켓을 막는 것은 그대로이고, 하네스 변경인 core 01만 그 앞에 선다. 결정(다섯 층과 포트)은 바뀌지 않는다.
