# 02: 묶음 형식과 `validate`의 파일 검사

**What to build:** 개발자가 `uv run python tools/search_eval.py validate <묶음 폴더>`를 치면, 도구가 데이터베이스 없이 묶음의 형식과 목록을 검사해 틀린 곳을 까닭과 함께 알리고 종료 코드 1을 낸다(스토리 20). 명령줄 도구의 입구와 종료 코드(0 문제 없음, 1 묶음이나 색인의 오류와 게이트 실패, 2 잘못된 인자)가 여기서 선다. 도구는 인자 해석과 조립만 하고, 묶음의 파일을 읽고 쓰는 코드는 `adapters`, 값과 판정은 `domain`과 `app`에 둔다(명세 "자리와 층"). 다른 하위 명령은 받는 티켓이 더한다.

**Blocked by:** 01 (포트 둘. 계약 티켓이 다른 티켓을 막는다)

**Status:** done

- [x] 묶음의 파일을 읽는다(명세 "평가 세트의 형식"): `eval-set.json`(`format_version` `"1.0.0"`. major가 다르면 거부), `config.json`의 칸 전부(`embedding_model`부터 `judge_prompt_version`까지), `documents.json`의 칸 전부(명세 "공공 문서 묶음"), 기대 근거(passage와 page 두 종류, `tags`), 질의 목록(`evidence_id`, `query`, 선택 칸 `filter`), `miss-review.jsonl`.
- [x] `validate`가 까닭과 함께 거부하는 것(시험마다 하나): 틀린 판, `id`와 `evidence_id`의 짝이 맞지 않음, 한 질의 목록 안의 같은 `evidence_id`, 모르는 유형 표지, 오프셋이 없는 필터 시각, `groups`가 든 필터, 기대 근거의 문서를 거르는 기간 필터, 없는 문서, 맞지 않는 해시, 목록에 없는 `documents/`의 파일, 문서 파일의 합 30MB 초과, 묶음 폴더 밖을 가리키는 경로(절대 경로, `..`가 든 경로, 밖을 가리키는 링크, 링크인 폴더).
- [x] 날짜를 시각으로 바꾸는 함수를 `adapters`에 하나 둔다. 문서 목록의 `updated_at`(`YYYY-MM-DD`)을 그날 00:00 `+09:00`으로 바꾸고, 03의 `index`가 같은 함수를 쓴다(명세 "날짜와 시각의 형식"). 기간 필터의 경계 시험은 이 바꾸기를 거친 값으로 쓴다. 문서의 날짜가 `updated_before`와 같으면 거부하고 `updated_after`와 같으면 받는다.
- [x] 경로 판정을 한 자리에 두어, 도구가 묶음에서 여는 모든 파일(머리가 가리키는 파일, `config.json`, `records/`와 그 안의 기록 파일, `judgments.jsonl`, `miss-review.jsonl`, 기준 보고서)에 읽을 때와 쓸 때 모두 걸 수 있게 한다. 07과 12가 쓰기에 같은 판정을 쓴다. 선례는 명세가 든 둘이다. `ingest` 명령이 폴더 밖을 가리키는 링크를 거르는 것과, `LocalBlobStore`가 키를 푼 경로가 데이터 폴더 밖이면 읽지도 쓰지도 않는 것이다.
- [x] 링크 시험은 그 플랫폼에서 권한 없이 만들 수 있는 링크로 짓고 skip하지 않는다(윈도는 junction, 리눅스는 심볼릭 링크. skip은 실패다. `.claude/rules/tests.md`). 개발 기계(윈도)와 CI(리눅스) 모두에서 링크 판정이 잡히는 것을 본다(명세 일지의 "다음", 티켓 세션의 명세 검토).
- [x] `README.md`의 트리와 `.scratch/plan-head.md`의 목표 배치에 `tools/search_eval.py`를 더한다.
- [x] 시험은 임시 폴더에 작은 묶음을 짓고 도구의 `main(argv)`를 부른다(선례 `tests/test_ingest_command.py`). 잘못된 인자는 2다.
- [x] 검사 넷이 초록이다.

## Comments

- 03의 `index`는 `adapters/eval_set_reader.py`의 `kst_midnight`와 `read_eval_set(BundlePaths)`가 낸 `EvalSet`(값은 `domain/eval_set.py`)을 쓴다. `validate`의 조립은 `adapters/eval_validate.py`의 `validate_bundle`이다.
- 07과 12가 묶음에 쓸 때는 `adapters/bundle_paths.py`의 `BundlePaths.resolve`를 지난 경로만 연다. 쓸 파일이 아직 없어도 풀리고, `documents/`처럼 하위 폴더 기준으로 풀려면 `under=`를 준다.
- `documents/` 안의 링크는 묶음 안을 가리켜도 거부한다(`BundlePaths`는 안을 가리키는 링크를 받는다). 문서는 실제 파일이어야 하고 걷기가 링크 안으로 내려가지 않기 때문이다. 명세는 밖을 가리키는 링크만 말한다.
- `BundlePaths`가 안을 가리키는 링크를 받는다는 것은 `documents/` 자체가 묶음 안의 다른 폴더를 가리키는 링크여도 받아 그 폴더를 문서 폴더로 걷는다는 뜻까지다(시험 `test_묶음_안을_가리키는_링크_폴더는_받는다`가 고정했다). 하드 링크는 판정이 가르지 못한다.
- 경로 판정은 마디의 `:`와 윈도 예약 장치 이름(`CON`, `NUL`, `COM1`과 확장자가 붙은 꼴)도 운영체제와 무관하게 글자로 거부한다. 쓰기 경로를 판정하는 07과 12도 같다.
- `miss-review.jsonl`의 `evidence_id`가 그 질의 목록의 질의에 드는지는 보지 않는다. 명세의 `validate` 목록에 그 짝이 없어 판정을 더하지 않았다.
- `documents.json`의 `bytes` 칸은 읽기만 하고 실제 파일 크기와 견주지 않는다. 해시가 내용을 가르고 명세의 `validate` 목록에 없다.
