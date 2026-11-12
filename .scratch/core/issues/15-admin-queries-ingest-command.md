# 15: 작업·문서 조회와 `ingest` 명령

**What to build:** 문서 담당자가 작업 ID로 수집이 끝났는지와 실패한 까닭을 보고, 문서 ID나 키로 문서 상태와 지식베이스마다의 색인 상태를 본다. 폴더 하나를 `rag-engine ingest <경로> --wait` 한 줄로 서버 없이 수집하고, 색인이 실패한 문서가 있으면 종료 코드로 안다.

**Blocked by:** 11 (삭제·되살림), 12 (재시도와 오류 번역)

**Status:** done

- [x] `GET /api/v1/admin/jobs/{job_id}`: 작업 행과 함께 그 문서의 결과(문서 조회와 같은 상태, 오류 코드, 지식베이스마다의 색인 상태)와 같은 문서에 대기·실행 중인 작업이 남았는지를 낸다. 없으면 404 `job_not_found`. 작업의 상태는 문서의 결과가 아니다(명세 "수집 파이프라인과 작업" 절의 넷째 단계).
- [x] `GET /api/v1/admin/jobs?status=&limit=&after=`(최근 순, 커서는 마지막 작업 ID), `GET /api/v1/admin/documents/{document_id}`(상태, 오류 코드, 지식베이스마다의 색인 상태와 조각 수, 메타데이터. 없으면 `document_not_found`), `GET /api/v1/admin/documents?status=&group=&key=&limit=&after=`(`key`는 그 키의 문서 하나를 찾는 필터). 커서 페이지는 UUIDv7의 ID 비교다.
- [x] `ingest <경로> [--group 이름] [--wait] [--timeout 초]`(명세 "관리 명령" 절): 파일 하나나 폴더를 받고, 폴더면 지원 확장자를 재귀로 걸으며 키는 폴더 기준 상대 경로(POSIX 구분자)다. 없는 그룹 이름이면 아무 파일도 넣지 않고 종료 코드 1. 파일마다 수집 유스케이스를 직접 불러 `action`을 한 줄씩 찍는다. 실행마다 UUIDv7 요청 ID 하나를 만들어 그 실행의 로그와 넣은 작업에 쓴다.
- [x] `--wait`: 넣은 문서마다(작업이 없는 `unchanged`·`restored`도) 그 문서의 대기·실행 중 작업이 없어질 때까지 폴링하고(작업자가 따로 떠 있어야 한다는 안내를 찍는다), 색인이 실패한 문서(문서 상태 `failed`이거나 살아 있는 판의 색인 상태에 `failed`)가 있으면 종료 코드 1, 그사이 지워진 문서는 실패로 세지 않는다. `--timeout`(기본 0, 무한)이 지나면 종료 코드 2.
- [x] HTTP 시험: 스토리 7, 8, 관리 API 열의 모양과 Problem Details(`job_not_found`, `document_not_found`, 422의 `errors`), 작업 조회가 그 문서의 결과와 같은 문서에 남은 작업을 냄(세대 대조에 걸려 `succeeded`로 끝난 작업도 뒤 작업이 남았으면 남았다고 낸다).
- [x] 관리 명령 시험: 스토리 9, `ingest --wait`의 종료 코드(넣은 작업이 세대 대조에 걸려 `succeeded`로 끝나도 같은 문서의 뒤 작업이 실패하면 1이고, `failed`로 끝나도 뒤 작업이 색인하면 0이며, 앞서 넣은 작업이 도는 문서를 다시 넣어 `unchanged`여도 그 작업을 기다린다), `--timeout`의 종료 코드 2, 없는 그룹의 종료 코드 1. 세대 대조 갈래 둘은 유스케이스 시험(`tests/app/test_await_documents.py`)이 재고, 명령 시험(`tests/test_ingest_command.py`)은 `unchanged`가 앞선 작업을 기다리는 갈래와 기다리는 사이 뒤 수집이 문서를 깨뜨려 실패하는 갈래를 잰다.
- [x] 검사 넷이 초록이다.
