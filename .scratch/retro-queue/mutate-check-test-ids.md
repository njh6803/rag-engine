# mutate-check-test-ids: 변이 표의 `tests`가 가리키는 시험 이름이 사라져도 `--check`가 지나간다

**상태:** 열림
**어디로:** `tools/mutate.py --check`(표의 `tests`가 가리키는 pytest 노드 식별자가 실제로 있는지 `pytest --collect-only`나 이름 검색으로 본다)
**승인:** 자체 승인 2026-11-14, 4회차(더하는 것이라 다섯 번째에 반영한다. 시험 이름을 바꾸는 쪽이 변이 표를 함께 고치는 일은 `implement` 스킬이 코드를 옮기거나 고쳤으면 `--check`를 돌리라고 이미 시키지만 그 검사가 이름을 보지 않는다), 일지 2026-11-14-2016-search-eval-07-inference-records.md(2회차: search-eval 12가 판정기 시험의 이름을 바꿔 변이 표 `eval_judge_mutations.toml`의 "SDK의 자체 재시도를 켠다"가 옛 이름을 가리켰고 PR 첫 봇 회차가 지적했다, 일지 2026-11-14-2147-search-eval-12-relevance-judge-claude.md), 2026-11-19-0025-glossary-ask-remaining-names.md(3회차: 임대를 작업 담당 기록으로 바꾸며 시험 이름 21개를 바꿨는데, 끝난 기능 core의 변이 표 `lease_worker_mutations.toml`의 `tests` 넷이 옛 이름을 가리켰다. 훑기가 `pyproject.toml`·`tools/`·`.github/`·`.claude/`만 보고 `.scratch/*/probes/`를 빼 일지에 "일치 없음"이라 적었고 셀프 리뷰의 명세 축이 잡았다. `--check`는 통과했고 `pytest --collect-only`는 종료 4였다), 2026-11-26-1938-admin-screens.md(4회차), ADR 불필요

search-eval 07이 05의 시험 `test_리랭커_끝점이_없는_전체_실행은_…`을 `test_기록을_끈_전체_실행은_…`으로 바꿨는데, 그 시험을 가리키던 05의 변이 표(`.scratch/search-eval/probes/eval_full_run_mutations.toml` 93행)를 함께 고치지 못했다. 셀프 리뷰의 명세 축이 잡았다. 옛 이름을 되살린 사본으로 `uv run python tools/mutate.py --check`를 돌리면 종료 0과 "변이 9 모두 원문이 한 번씩 있다"만 나와(2026-11-14 손으로 쟀다), 이름의 존재는 보지 않는다. 죽은 이름은 변이를 실제로 돌리는 때(수 분 뒤)에야 기준선 오류로 드러난다.
