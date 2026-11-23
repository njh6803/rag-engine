# 02: 건너뜀

**What to build:** 암호가 걸린 파일과 글자가 없는 파일(스캔본처럼 색인할 글이 하나도 나오지 않는 파일)이 실패가 아니라 건너뜀(`skipped`)으로 남는다. 운영자는 관리 API의 문서 목록에서 `status=skipped`로 그 문서를 따로 거르고, 문서마다 까닭(`encrypted`, `no_text`)을 본다. 같은 파일을 다시 보내면 다시 파싱하지 않고 `unchanged`로 답한다. 이미 설치된 곳의 암호 실패 문서와 글자 없는 문서는 마이그레이션이 건너뜀으로 옮긴다. 밀어 넣는 원천의 문서에도 같은 상태를 쓰므로 이 티켓은 원천 기능 없이 수집 API만으로 돈다(스토리 27).

**Blocked by:** 01 (커넥터 인터페이스 1.0과 이 기능의 스키마)

**Status:** done

- [x] 명세 "티켓을 나눌 때 함께 둘 것"의 건너뜀 묶음 넷을 이 티켓에 함께 둔다. 건너뜀으로 옮기는 마이그레이션, 색인 작업이 건너뜀을 쓰는 변경, 관리 API의 문서 목록이 건너뜀을 보이는 변경, 수집 API가 건너뜀 문서에 `unchanged`로 답하는 변경이다.
- [x] 문서 상태에 `skipped`를, 문서에 건너뜀 사유(`encrypted`, `no_text`. 상태가 `skipped`일 때만 있다)를 더한다(명세 "건너뜀"). 표의 칸과 상태 값은 01의 마이그레이션이 만들어 두었다.
- [x] 파서가 암호가 걸린 파일을 알리면(파서 인터페이스는 바꾸지 않는다) 색인 작업은 문서 상태를 `skipped`와 `encrypted`로 쓰고 성공으로 끝난다. 파싱 결과에서 색인할 글이 하나도 나오지 않으면(공백만 있는 것도 같다) `skipped`와 `no_text`다. 어느 쪽이든 대상 판마다 그 문서의 옛 조각을 지우고 색인 상태를 `indexed`로 쓰고(조각 0개) 마지막에 전환 검사를 한다(명세 "건너뜀"). 수집 API의 갱신은 옛 조각을 지우지 않고 색인 작업이 갈아 끼우므로(`app/ingest.py`가 조각 표의 조각을 지우는 자리는 그룹이 바뀌어 문서가 지식베이스에서 빠질 때뿐이고, 색인 작업이 `VectorIndex.replace_chunks`로 옛 조각을 새 조각으로 바꾼다), 지금의 실패 경로(`mark_version_failed`가 `delete_chunks`를 먼저 부른다)처럼 건너뜀 경로도 옛 조각을 지워야 바뀐 내용이 검색에 옛 글로 남지 않는다. 오류 코드 `encrypted_document`는 문서, 색인 상태, 작업 행의 오류 코드 칸에 더는 쓰이지 않고 파서의 신호로만 남는다(명세 "오류 코드").
- [x] 건너뜀 문서와 내용이 같은 파일을 수집 API로 다시 보내면 `unchanged`이고 작업이 들어가지 않는다. 내용이 다르면 보통의 갱신이고 문서 상태가 `received`로 돌아간다(명세 "건너뜀", "수집 API"). 암호 실패 문서에 `requeued`로 답하던 지금의 계약이 `unchanged`로 바뀌는 것은 명세가 적은 계약 변경이고, 응답이 받는 값의 목록은 그대로다.
- [x] 데이터만 옮기는 마이그레이션 하나(번호는 01의 마이그레이션 다음 번호. 01이 0004를 쓰면 0005다)가 문서 상태 `failed`와 오류 코드 `encrypted_document`인 문서를 `skipped`와 `encrypted`로, 저장된 파싱 결과에 글이 없는 문서(지금은 `parsed`이고 조각 0개)를 `skipped`와 `no_text`로 옮기고, 그 문서의 색인 상태를 `indexed`와 오류 코드 없음으로 맞춘다(명세 "데이터 모델과 스키마"의 마지막 항목). 옛 스키마에 두 문서를 만들어 두고 올린 뒤 옮겨졌는지 보는 시험을 둔다(명세 "Testing Decisions"의 마이그레이션 항목). 이 티켓의 PR 제목에는 느낌표를 붙인다(ADR 0020).
- [x] 관리 API의 문서 목록이 상태로 거르는 값에 `skipped`를 받고 문서 응답에 `skip_reason`을 싣는다(명세 "관리 API"). 응답 모델의 머리 설명이 문서 상태를 넷이라고 적은 것을 고친다(명세 "규약 문서와 낡은 문장", ADR 0022 Consequences).
- [x] 지금 암호 실패를 기대하는 시험을 건너뜀의 기대로 고친다. `tests/contract/test_ingest_updates.py`(암호 PDF를 다시 보내는 장면은 이제 `unchanged`를 기대한다), `tests/app/test_parse_pipeline.py`의 `test_암호가_걸린_PDF는_작업과_문서에_encrypted_document를_남긴다`, `tests/app/test_job_retry.py`, `tests/app/test_ingest_group_requeue.py`, `tests/app/test_index_document.py`, 그리고 `tests/support/interleaving.py`의 기본값처럼 `encrypted_document`나 암호 실패의 `requeued`를 기대하는 자리다. 파서 층의 시험(`tests/adapters/test_parse_runner.py` 같은 것)은 파서가 지금처럼 `encrypted_document`를 알린다는 것이라 그대로다. 고치기 전에 `encrypted_document`와 `requeued`를 grep해 빠진 자리가 없는지 본다.
- [x] 시험(주 이음매): 암호가 걸린 PDF와 글자가 없는 PDF를 수집 API로 넣고 작업자를 돌리면 문서 상태가 `skipped`이고 사유가 실리며 작업은 `succeeded`이고, 문서 목록의 `status=skipped`에 나온다. 같은 내용을 다시 보내면 `unchanged`이고 작업이 들어가지 않는다. 재색인을 시작한 지식베이스에서 건너뜀 문서의 색인 작업을 마지막에 돌리면 새 색인 판으로 전환된다. 글이 있어 검색에 나오던 문서를 같은 키의 암호 PDF로 바꿔 보내고 작업자를 돌리면, 상태가 `skipped`이고 옛 글이 검색에 나오지 않는다(PR 직전 리뷰가 냈다). 글자가 없어 건너뛴 문서를 둔 채 글을 내는 가짜 파서(파서 버전이 다르다)로 바꿔 끼우고 재색인하면 그 문서가 검색에 나오고 상태가 `skipped`가 아니다(명세 "Testing Decisions"의 장면 표).
- [x] 검색 도구의 형식은 바뀌지 않는다. MCP 클라이언트로 접속하는 지금의 계약 시험이 그대로 초록이다(원칙 VII).
- [x] 검사 넷이 초록이다. 원칙 II는 `tools/check_type_escapes.py`가 판정한다.
