# 08: PDF·HWPX 파서와 파싱의 격리·자원 한도

**What to build:** PDF와 HWPX 문서도 색인되고, 암호가 걸렸거나 깨졌거나 악의적인 문서(압축 폭탄, 쪽이 수만 장인 PDF)는 작업자를 죽이지 않고 까닭 코드와 함께 실패로 끝난다. 실패한 문서를 고쳐 다시 넣으면 다시 색인된다.

**Blocked by:** 07 (첫 왕복)

**Status:** ready-for-agent

- [ ] PDF 파서(pdfplumber): 쪽마다 줄을 읽어 빈 줄로 문단을 가르고 표 추출로 표 블록을 내며 쪽 번호(1부터)를 붙인다. 암호는 인터페이스 예외(`encrypted_document`), 쪽 수 초과는 인터페이스 예외(`too_many_pages`)다.
- [ ] HWPX 파서(python-hwpx): 문단과 표, 개요 수준이 있는 문단을 제목으로. 글이 없는 문서는 `parsed`이고 조각이 0개다.
- [ ] 자식 프로세스 실행기: `RAG_PARSE_TIMEOUT_SECONDS`를 넘기면 죽이고 `parse_timeout`, 메모리 한도나 `MemoryError`는 `parse_memory_exceeded`(리눅스 `RLIMIT_AS`, Windows는 걸지 않고 기록), 그 밖의 예외는 `parse_failed`. 리눅스(CI)에서 `RLIMIT_AS` 기본값(`RAG_PARSE_MEMORY_MB` 2048) 아래의 자식이 파서 셋을 import하고 픽스처를 파싱하는 것을 본다(명세 검토가 재지 못한 것이다). 파싱 결과를 받은 뒤 글 크기(`document_too_large`)를 보고 U+0000을 지운다(프로브 `.scratch/core/probes/pg-ddl/ddl_locks.py`의 E).
- [ ] ZIP 사전 검사(부모가 목록만 읽는다): 항목 4096개, 압축 해제 합계, 1MiB를 넘는 항목의 압축비, 암호 항목(명세 "파싱의 격리와 자원 한도" 절).
- [ ] 파싱의 영구 실패 종결: 문서 상태 `failed`와 오류 코드, 살아 있는 판의 조각을 지우고 색인 상태 `failed`, 작업은 재시도 없이 `failed`. 세대가 다르면 문서 쪽을 건드리지 않고 작업만 `failed`. 전환 검사를 부르는 자리를 둔다(14가 채운다).
- [ ] major가 다른 파서를 entry point에서 거부하고 기록한다(스토리 41).
- [ ] 시험: PDF·HWPX 왕복, 영구 실패의 즉시 `failed`(고친 파일을 넣으면 `received`를 거쳐 `parsed`, 그 뒤 같은 내용은 `unchanged`), 내용을 바꿨다가 옛 내용으로 되돌려 파싱을 건너뛰어도 `parsed`로 돌아옴, 자식 프로세스의 시간 초과·예외·메모리 한도(한 시험이 플랫폼에 따라 갈래로 단언한다. skip이 아니다), 스토리 10, 36.
- [ ] 픽스처: 글이 든 작은 PDF 하나는 저장소에 두고, 암호 PDF·압축 폭탄 ZIP·쪽이 많은 PDF는 시험이 만든다.
- [ ] 검사 넷이 초록이다.
