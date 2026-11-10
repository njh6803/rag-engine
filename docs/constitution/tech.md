# rag-engine 헌법 · 스택

의존성을 더하거나 스택을 바꿀 때 읽는다. 갈아 끼우는 데 큰 비용이 드는 의존성(데이터베이스, 벡터 저장소, 작업 대기열, 파서, 임베딩 모델, MCP SDK, 웹 프레임워크)을 더하거나 바꾸면 ADR을 남긴다.

| 항목 | 값 |
|---|---|
| 언어 | Python 3.12 고정 (`requires-python = "==3.12.*"`) |
| 패키지 관리 | uv, 단일 패키지, src 레이아웃(`src/rag_engine/`) |
| 린트·포맷 | ruff |
| 타입 | pyright strict. 우회의 판정은 원칙 II |
| 테스트 | pytest. HTTP 표면은 `httpx`로 민다. 검색 도구의 형식은 공식 MCP SDK의 클라이언트로 HTTP 접속하는 계약 시험이 본다(원칙 VII). 테스트용 PostgreSQL은 Docker로 통일한다. CI는 `pgvector/pgvector:0.8.7-pg18-trixie` service container(운영과 같은 판, ADR 0006), 로컬은 `compose.test.yml`의 같은 이미지이고, 테스트는 `RAG_TEST_DATABASE_URL`이 가리키는 데이터베이스를 쓰며 없으면 skip이 아니라 실패한다(원칙 I). 검사 러너(`tools/run_checks.py`)는 pytest를 돌리기 전에 서버가 안 보이면 `compose.test.yml`을 띄우고 준비를 기다리며, 띄운 컨테이너는 내리지 않고 남긴다. 손으로 치는 `uv run pytest`는 띄우지 않는다 |
| HTTP와 MCP | FastAPI와 uvicorn. REST(관리 API, 수집 API)와 MCP를 한 프로세스의 한 앱이 연다. MCP는 공식 SDK `mcp`(major 2로 묶는다)의 Streamable HTTP 앱을 `/mcp`에 붙인다. ADR 0005. 전송은 설정 `RAG_MCP_STATELESS`(기본 true)와 `RAG_MCP_JSON_RESPONSE`(기본 false)로 고르고 기본은 세션 없음 + SSE 응답이다. 허용 호스트 설정은 필수다(ADR 0014). 파일 업로드는 `python-multipart` |
| 데이터베이스 | PostgreSQL 18. compose가 동봉한 것 하나만 지원하고(ADR 0002 이력 2026-11-09) 연결 문자열 하나만 받는다. 접근은 SQLAlchemy 2.1 Core 비동기(psycopg 3, greenlet), 마이그레이션은 alembic이고 `rag-engine migrate`가 돌린다. ADR 0011 |
| 벡터 저장소 | pgvector 0.8.x(자기 PostgreSQL)와 PostgreSQL 전문 검색. 한국어 형태소 분석은 앱의 kiwipiepy(Apache-2.0, 우리 스텁)가 하고 `to_tsvector('simple', …)`에 넣는다. 벡터와 키워드는 한 SQL에서 RRF로 합친다. ADR 0006 |
| 작업 대기열 | PostgreSQL 작업 표(SKIP LOCKED + LISTEN/NOTIFY). 작업자는 검색 서버와 다른 프로세스·이미지다. ADR 0009 |
| 파서, 임베딩, 리랭커 | 파서는 pdfplumber(PDF), python-docx(DOCX), python-hwpx(HWPX, 1.0의 HWP 5.0도 같은 라이브러리). 설치형으로 재배포하므로 라이선스(특히 GPL과 AGPL 계열)를 원문으로 확인한 것만 들인다. PyMuPDF와 pyhwp는 AGPL이라 들이지 않는다. 임베딩과 리랭커는 설치 안의 TEI(text-embeddings-inference) 컨테이너가 돌리고(기본 bge-m3, bge-reranker-v2-m3) 서버·작업자 이미지에는 torch가 없다. 호출은 `/v1/embeddings`, `/tokenize`, `/rerank`. ADR 0010 |
| 설정 | pydantic-settings. 환경 변수 `RAG_*`, `.env`, 비밀 파일. ADR 0015 |
| 관리자 페이지 | admin 설계 인터뷰가 정한다(pnpm과 Next의 웹 워크스페이스, 또는 서버가 그리는 단순한 화면). 정하면 ADR과 함께 이 칸을 고친다 |
| 관리 명령 | 표준 라이브러리 argparse. 범위는 서버 없이 해야 하는 것(`serve`, `worker`, `migrate`, `bootstrap-token`)과 `ingest <경로>`이고, 나머지 쓰기는 관리 API다. 명령은 REST와 같은 app 층 유스케이스를 부르고 같은 연결 문자열로 데이터베이스에 직접 붙는다(ADR 0007) |
| 컨테이너 | Docker 이미지. 서버와 작업자 이미지 둘(ADR 0007). 컨테이너는 root가 아닌 사용자로 돈다. 단독 compose의 기본 컨테이너는 서버, 작업자, PostgreSQL, 임베딩 TEI, 리랭커 TEI 다섯이고 메모리 예산은 32GB 기준(최소 16GB). 판 태그, 단독 compose, SBOM과 CVE 스캔은 release-image가 정한다 |
| 원격·CI | GitHub, GitHub Actions(ubuntu, uv). 로컬 훅과 같은 검사, 계약 시험, 이미지 빌드가 돌고 필수 검사 `verify`가 결과를 모은다(`docs/constitution/operations.md`) |
| 로깅 | 표준 라이브러리 logging에 우리 포매터를 붙여 JSON Lines를 stdout으로 낸다(ADR 0015). 무엇을 남기지 않는지는 원칙 V |

파이썬 한 패키지를 유지하고 배포가 갈릴 때만 나눈다. 관리자 페이지를 웹 워크스페이스로 짓게 되면 파이썬(`src/`)과 노드(`web/`)의 루트를 나눈다.
