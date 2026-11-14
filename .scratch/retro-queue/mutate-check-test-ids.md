# mutate-check-test-ids: 변이 표의 `tests`가 가리키는 시험 이름이 사라져도 `--check`가 지나간다

**상태:** 열림
**어디로:** `tools/mutate.py --check`(표의 `tests`가 가리키는 pytest 노드 식별자가 실제로 있는지 `pytest --collect-only`나 이름 검색으로 본다)
**승인:** 자체 승인 2026-11-14, 1회차(더하는 것이라 다섯 번째에 반영한다. 시험 이름을 바꾸는 쪽이 변이 표를 함께 고치는 일은 `implement` 스킬이 코드를 옮기거나 고쳤으면 `--check`를 돌리라고 이미 시키지만 그 검사가 이름을 보지 않는다), 일지 2026-11-14-2016-search-eval-07-inference-records.md, ADR 불필요

search-eval 07이 05의 시험 `test_리랭커_끝점이_없는_전체_실행은_…`을 `test_기록을_끈_전체_실행은_…`으로 바꿨는데, 그 시험을 가리키던 05의 변이 표(`.scratch/search-eval/probes/eval_full_run_mutations.toml` 93행)를 함께 고치지 못했다. 셀프 리뷰의 명세 축이 잡았다. 옛 이름을 되살린 사본으로 `uv run python tools/mutate.py --check`를 돌리면 종료 0과 "변이 9 모두 원문이 한 번씩 있다"만 나와(2026-11-14 손으로 쟀다), 이름의 존재는 보지 않는다. 죽은 이름은 변이를 실제로 돌리는 때(수 분 뒤)에야 기준선 오류로 드러난다.
