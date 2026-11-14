# mutate-concurrent-runs: 변이 도구를 같은 체크아웃에서 둘 겹쳐 돌려도 아무것도 막지 않아 한쪽이 소스에 변이를 남긴 채 끝난다

**상태:** 열림
**어디로:** `tools/mutate.py`(시작할 때 체크아웃 안에 표지 파일과 pid를 두고, 그 pid가 살아 있으면 둘째 실행이 소스를 건드리기 전에 거부한다. 첫째 실행이 끝나거나 죽으면 표지를 치운다. `pytest-during-mutate`의 훅이 읽을 표지를 같은 파일로 쓸 수 있는지 처방을 정할 때 함께 본다)
**승인:** 자체 승인 2026-11-14, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-14-1917-search-eval-06-miss-causes-and-breakdowns.md, ADR 불필요

search-eval 06 세션이 변이 표를 백그라운드로 돌리다 환경 변수 누락으로 기준선이 오류가 나서 멈추려 했다. 이 Windows 셸에는 `pkill`이 없어 첫 실행이 계속 돌았고, 환경 변수를 붙여 다시 돌린 둘째 실행과 `src/rag_engine/app/eval_run.py`를 겹쳐 고쳤다. 첫 표가 "되돌리지 못했다"로 종료 코드 3을 냈고 `if not diagnosis.is_current:`가 `if False:`로 소스에 남았다. 한 줄을 손으로 되돌린 뒤 변이 표 다섯의 `--check`와 `if False:` 검색으로 남은 변이가 없는 것을 확인했고, 두 표를 겹침 없이 처음부터 다시 돌렸다. 잃은 것은 시간이고 데이터는 아니다. 변이 도구를 백그라운드로 멈추는 Windows 쪽 길(`Get-CimInstance Win32_Process`로 찾아 `Stop-Process`)은 도구가 아니라 환경의 사실이라 이 항목의 처방이 아니다. `pytest-during-mutate`는 같은 도구를 다루지만 겹치는 상대가 pytest이고 처방이 훅이라 따로 둔다.
