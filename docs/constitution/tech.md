# rag-engine 헌법 · 스택

의존성을 더하거나 스택을 바꿀 때 읽는다. 갈아 끼우는 데 큰 비용이 드는 의존성(데이터베이스, 벡터 저장소, 작업 대기열, 파서, 임베딩 모델, MCP SDK, 웹 프레임워크)을 더하거나 바꾸면 ADR을 남긴다.

| 항목 | 값 |
|---|---|
| 언어 | Python 3.12 고정 (`requires-python = "==3.12.*"`) |
| 패키지 관리 | uv, 단일 패키지, src 레이아웃(`src/rag_engine/`) |
| 린트·포맷 | ruff |
| 타입 | pyright strict. 우회의 판정은 원칙 II |
| 테스트 | pytest. HTTP 표면은 `httpx`로 민다. 검색 도구의 형식은 공식 MCP SDK의 클라이언트로 HTTP 접속하는 계약 시험이 본다(원칙 VII) |
| HTTP와 MCP | FastAPI와 uvicorn. REST(관리 API, 수집 API)와 MCP를 한 프로세스의 한 앱이 연다. MCP는 공식 SDK `mcp`(major 2로 묶는다)의 Streamable HTTP 앱을 `/mcp`에 붙인다. ADR 0005 |
| 데이터베이스 | PostgreSQL. 이 서버의 데이터베이스이고 연결 문자열 하나만 받으며, 마이그레이션은 이 저장소가 한다. ADR 0002. 마이그레이션 도구는 core 설계 인터뷰가 정한다 |
| 벡터 저장소 | pgvector(자기 PostgreSQL)와 별도 벡터 DB 가운데 core 설계 인터뷰가 정한다. 기준은 접근 그룹과 날짜로 거르는 필터, 한국어 키워드 검색과의 결합, 설치 환경의 PostgreSQL에 붙일 때 확장(pgvector, pg_bigm, PGroonga 등)이 있어야 하는 문제다. 정하면 ADR과 함께 이 칸을 고친다 |
| 작업 대기열 | 수집 작업자를 검색 서버와 다른 프로세스로 나누는 방식을 core 설계 인터뷰가 정한다. 정하면 ADR과 함께 이 칸을 고친다 |
| 파서, 임베딩, 리랭커 | core 설계 인터뷰가 정한다. 설치형으로 재배포하므로 라이선스(특히 GPL과 AGPL 계열)를 원문으로 확인한 것만 들인다. 임베딩과 리랭커는 로컬에서 돈다 |
| 관리자 페이지 | admin 설계 인터뷰가 정한다(pnpm과 Next의 웹 워크스페이스, 또는 서버가 그리는 단순한 화면). 정하면 ADR과 함께 이 칸을 고친다 |
| 관리 명령 | 표준 라이브러리 argparse |
| 컨테이너 | Docker 이미지. 컨테이너는 root가 아닌 사용자로 돈다. 판 태그, 단독 compose, SBOM과 CVE 스캔은 release-image가 정한다 |
| 원격·CI | GitHub, GitHub Actions(ubuntu, uv). 로컬 훅과 같은 검사, 계약 시험, 이미지 빌드가 돌고 필수 검사 `verify`가 결과를 모은다(`docs/constitution/operations.md`) |
| 로깅 | 표준 라이브러리 logging. 무엇을 남기지 않는지는 원칙 V |

파이썬 한 패키지를 유지하고 배포가 갈릴 때만 나눈다. 관리자 페이지를 웹 워크스페이스로 짓게 되면 파이썬(`src/`)과 노드(`web/`)의 루트를 나눈다.
