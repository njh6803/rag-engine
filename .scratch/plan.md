<!-- 이 파일은 도구가 만든다. 기능 계획(`.scratch/<slug>/plan.md`)이나 `.scratch/plan-head.md`를 고치고 `uv run python tools/plan_table.py`를 돌린다. -->
# 전체 계획

규약(기능 하나에 디렉터리 하나, 프론티어, 계약 티켓, 상태 전이)은 `docs/agents/issue-tracker.md`의 전체 계획 절이 원천이다. 순서와 범위의 근거는 킥오프 입력 `.scratch/kickoff-input.md`(rag-engine 계획 제안, 2026-11-06)의 6절과 `docs/journal/`에 있다. 첫 슬라이스의 범위는 아래 목표 배치 뒤에 있다.

아래 기능 표와 프론티어는 도구가 기능 계획에서 만든다. 기능 계획 `.scratch/<slug>/plan.md`나 이 파일(`.scratch/plan-head.md`)을 고치고 `uv run python tools/plan_table.py`를 돈다. 기능의 상태는 손으로 적지 않고 기능 계획의 `끝` 줄과 티켓의 `Status:`에서 정해진다.

## 순서

core 다음은 release-image와 search-eval이다. 판을 고정한 이미지가 있어야 클라이언트가 실제 서버로 시험할 수 있고, 공개 문서 묶음을 넣은 공개 시연을 동기화와 관리자 페이지보다 먼저 열 수 있기 때문이다. 공개 시연은 관리 명령으로 문서를 한 번 넣고 동기화를 쓰지 않으므로, core, search-eval, release-image 셋이면 된다. 그래서 source-sync는 release-image 뒤에 서고, 뒤에 오는 행은 release-image가 정한 판 태그와 단독 compose의 규칙으로 자기 몫(source-sync는 원천 폴더의 볼륨, admin은 관리자 페이지의 이미지)을 더한다. backup-upgrade와 diag-bundle은 원천 설정과 동기화 기록을 다루므로 source-sync 뒤에 선다.

이정표는 `docs/PRD.md`의 성공의 정의가 원천이다. 공개 시연(2027-01 초)은 core, search-eval, release-image, 0.1(2027-03 초 무렵)은 슬라이스 2까지, 1.0(2027년 상반기, 어림)은 슬라이스 3까지다.

## 목표 배치

슬라이스가 끝날 때마다 채워진다. 골격은 킥오프 7단계가 헌법(`docs/constitution/tech.md`)대로 세웠고, 현재 트리는 `README.md`다. 아래에서 슬라이스 표시가 없는 줄은 킥오프 골격에 이미 있다. 정하지 않은 배치는 그것을 정할 설계 인터뷰를 적는다.

```
src/rag_engine/
  main.py                  관리 명령(argparse). serve → server. core 가 수집 명령을 더한다
  server.py                create_app() 하나가 FastAPI 앱을 조립한다. /health, MCP 하위 앱(/mcp, ADR 0005)
  (수집·색인·검색의 층)    슬라이스 1. core 설계 인터뷰가 층, 플러그인 자리 셋(커넥터·변환·파서, ADR 0003)의 인터페이스, 벡터 저장소, 작업 대기열, 마이그레이션 도구를 정한다
tests/contract/            MCP 계약 시험. core 가 검색 도구의 형식을 더한다(원칙 VII)
Dockerfile                 이미지 짓기. 슬라이스 2의 release-image 가 판 태그, 단독 compose, SBOM과 CVE 스캔을 더한다
(관리자 페이지)            슬라이스 2. admin 설계 인터뷰가 화면 스택을 정한다. 웹 워크스페이스면 web/ 에 두고 파이썬과 루트를 나눈다(tech.md)
```

첫 슬라이스: 표본 문서 폴더를 관리 API로 수집하면 서버가 PDF, DOCX, HWPX를 파싱, 청킹, 임베딩해 색인을 만들고, MCP 클라이언트가 같은 서버의 `/mcp`(Streamable HTTP)로 접속해 검색 도구를 부르면 근거 위치와 갱신일이 붙은 조각을 받는다. MCP 도구 목록에는 쓰기 도구가 없고, 수집 중에도 검색이 응답한다. 첫 슬라이스가 끝나기 전에는 만들지 않는 것: 원천과 동기화(커넥터 플러그인, 주기 실행, 정리 작업), 관리자 페이지, 이미지와 단독 compose, 스캔본 OCR과 HWP 5.0 바이너리, 접근 그룹으로 거르는 검색(칸은 처음부터 두고 채우기만 한다), 답 생성.

| 슬라이스 | 기능 | 내용 | Blocked by | Status |
|---|---|---|---|---|
| 1 | [core](core/plan.md) | 수집, 색인, 검색의 본체 v0. 관리 API로 넣은 문서를 MCP 읽기 도구로 근거 위치와 갱신일이 붙은 조각으로 찾는다 | 없음 | todo |
| 2 | [admin](admin/plan.md) | 관리자 페이지 v0. 현황, 원천, 문서, 검색 시험 화면에서 문서를 올리고 지우며 잘 찾아지는지 확인한다 | source-sync | todo |
| 2 | [backup-upgrade](backup-upgrade/plan.md) | 색인, 원본 문서, 데이터베이스를 명령 하나로 백업하고 복원하며, 판 올림 때 다시 색인해야 하는지 알린다 | source-sync | todo |
| 2 | [diag-bundle](diag-bundle/plan.md) | 진단 묶음 명령. 판, 색인 상태, 원천의 동기화 기록, 검색 지연을 비밀 없이 한 파일로 묶는다 | source-sync | todo |
| 2 | [release-image](release-image/plan.md) | 판마다 검색 서버와 수집 작업자의 이미지를 내고, 자기 PostgreSQL을 띄우는 단독 compose로 깨끗한 VM에 설치된다 | core | todo |
| 2 | [search-eval](search-eval/plan.md) | 평가 세트로 검색의 상위 k개 적중률을 재고, 기준치 아래로 떨어지면 CI가 실패한다 | core | todo |
| 2 | [source-sync](source-sync/plan.md) | 원천(업로드, 서버 경로, 수집 API)과 동기화. 원천에서 더하고 고치고 지운 문서가 다음 동기화 뒤 검색에 반영된다 | core, release-image | todo |
| 3 | [change-log](change-log/plan.md) | 관리 변경 기록. 누가 언제 문서, 원천, 설정, 접근 그룹을 바꿨는지 남기고 조회하고 내보낸다 | admin | todo |
| 3 | [db-source](db-source/plan.md) | SQL 커넥터. 운영자가 쓴 질의와 매핑으로 데이터베이스에 든 글과 그 첨부를 문서로 수집한다 | source-sync | todo |
| 3 | [doc-freshness](doc-freshness/plan.md) | 문서의 갱신일과 시행일을 관리하고, 기한이 지난 문서의 조각에 "오래됨"을 표시한다 | admin | todo |
| 3 | [doc-permission](doc-permission/plan.md) | 문서 묶음별 접근 그룹으로 검색을 거르고, MCP `_meta`에 주체가 없는 요청은 거부한다 | admin | todo |
| 3 | [hwp-binary](hwp-binary/plan.md) | HWP 5.0 바이너리(표 포함)를 파싱해 본문과 표의 칸이 근거 위치와 함께 검색된다 | admin | todo |

## 프론티어

done 이 아니고, Blocked by 가 비었거나 막는 기능이 모두 done 인 기능이다. `core`
