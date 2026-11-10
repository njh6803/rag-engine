# 전체 계획

규약(기능 하나에 디렉터리 하나, 프론티어, 계약 티켓, 상태 전이)은 `docs/agents/issue-tracker.md`의 전체 계획 절이 원천이다. 순서와 범위의 근거는 킥오프 입력 `.scratch/kickoff-input.md`(rag-engine 계획 제안, 2026-11-06)의 6절과 `docs/journal/`에 있다. 첫 슬라이스의 범위는 아래 목표 배치 뒤에 있다.

아래 기능 표와 프론티어는 도구가 기능 계획에서 만든다. 기능 계획 `.scratch/<slug>/plan.md`나 이 파일(`.scratch/plan-head.md`)을 고치고 `uv run python tools/plan_table.py`를 돈다. 기능의 상태는 손으로 적지 않고 기능 계획의 `끝` 줄과 티켓의 `Status:`에서 정해진다.

## 순서

core 다음은 release-image와 search-eval이다. 판을 고정한 이미지가 있어야 클라이언트가 실제 서버로 시험할 수 있고, 공개 문서 묶음을 넣은 공개 시연을 동기화와 관리자 페이지보다 먼저 열 수 있기 때문이다. 공개 시연은 관리 명령으로 문서를 한 번 넣고 동기화를 쓰지 않으므로, core, search-eval, release-image 셋이면 된다. 그래서 source-sync는 release-image 뒤에 서고, 뒤에 오는 행은 release-image가 정한 판 태그와 단독 compose의 규칙으로 자기 몫(source-sync는 원천 폴더의 볼륨, admin은 관리자 페이지의 이미지)을 더한다. backup-upgrade와 diag-bundle은 원천 설정과 동기화 기록을 다루므로 source-sync 뒤에 선다.

이정표는 `docs/PRD.md`의 성공의 정의가 원천이다. 공개 시연(2027-01 초)은 core, search-eval, release-image, 0.1(2027-03 초 무렵)은 슬라이스 2까지, 1.0(2027년 상반기, 어림)은 슬라이스 3까지다.

core부터 테스트는 Docker로 띄운 PostgreSQL(pgvector)이 있어야 돌고 없으면 실패하므로(`docs/constitution/tech.md` 테스트 칸), 검사 러너가 테스트 DB를 띄우는 변경은 core의 첫 티켓(core 01)이고 나머지 core 티켓은 그 티켓 뒤에 선다(설계 일지는 하네스 티켓으로 적었지만 2026-11-10 티켓 세션에서 사용자가 core 01로 골랐다. core 명세 Further Notes). 러너가 pytest를 always_run으로 돌리므로 그 변경 뒤에는 문서 PR과 하네스 chore를 포함한 모든 커밋에 Docker가 필요하고, Docker가 없는 클라우드 세션은 커밋할 수 없다. 이 분기는 core 01이 next-session 결정표 아래의 Docker 갈래로 더했다.

## 목표 배치

슬라이스가 끝날 때마다 채워진다. 골격은 킥오프 7단계가 헌법(`docs/constitution/tech.md`)대로 세웠고, 현재 트리는 `README.md`다. 아래에서 슬라이스 표시가 없는 줄은 킥오프 골격에 이미 있다. 정하지 않은 배치는 그것을 정할 설계 인터뷰를 적는다.

```
src/rag_engine/
  main.py                  관리 명령(argparse). serve → server. core 가 worker, migrate, bootstrap-token, ingest <경로> 를 더한다(ADR 0007·0011·0014)
  server.py                create_app() 하나가 FastAPI 앱을 조립한다. /health, REST(/api/v1/admin, /api/v1/ingest, ADR 0015), MCP 하위 앱(/mcp, ADR 0005). 조립만 하고 유스케이스는 app 에
  worker/                  슬라이스 1. 작업자 조립. 작업 대기열에서 작업을 꺼내 수집 파이프라인을 돈다(ADR 0009)
  adapters/                슬라이스 1. PostgreSQL(SQLAlchemy·alembic·pgvector·Kiwi), TEI, 파서, 커넥터, 작업 대기열, 파일 저장소(ADR 0006·0010·0011·0013)
  app/                     슬라이스 1. 유스케이스(수집, 동기화, 검색, 재색인, 삭제, 토큰). 포트만 부른다
  domain/                  슬라이스 1. 엔티티와 포트 Protocol(ADR 0007·0008·0012). 층의 경계는 import-linter 계약
tests/contract/            MCP 계약 시험. core 가 검색 도구의 형식(format_version, ADR 0015)과 쓰기 도구 없음을 더한다(원칙 VII, ADR 0001)
compose.test.yml           슬라이스 1. 테스트 PostgreSQL(pgvector/pgvector:0.8.7-pg18-trixie, 운영과 같은 판). 검사 러너가 없으면 띄운다(core 01)
Dockerfile                 이미지 짓기(서버와 작업자 둘, ADR 0007). 슬라이스 2의 release-image 가 판 태그, 단독 compose(서버, 작업자, PostgreSQL, 임베딩 TEI, 리랭커 TEI), SBOM과 CVE 스캔을 더한다
(관리자 페이지)            슬라이스 2. admin 설계 인터뷰가 화면 스택을 정한다. 웹 워크스페이스면 web/ 에 두고 파이썬과 루트를 나눈다(tech.md)
```

첫 슬라이스: 표본 문서 폴더를 관리 API로 수집하면 서버가 PDF, DOCX, HWPX를 파싱, 청킹, 임베딩해 색인을 만들고, MCP 클라이언트가 같은 서버의 `/mcp`(Streamable HTTP)로 접속해 검색 도구를 부르면 근거 위치와 갱신일이 붙은 조각을 받는다. MCP 도구 목록에는 쓰기 도구가 없고, 수집 중에도 검색이 응답한다. 첫 슬라이스가 끝나기 전에는 만들지 않는 것: 원천과 동기화(커넥터 플러그인, 주기 실행, 정리 작업), 관리자 페이지, 이미지와 단독 compose, 스캔본 OCR과 HWP 5.0 바이너리, 접근 그룹으로 거르는 검색(칸은 처음부터 두고 채우기만 한다), 답 생성.
