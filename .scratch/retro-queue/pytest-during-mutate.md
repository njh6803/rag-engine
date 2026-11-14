# pytest-during-mutate: 변이 도구가 도는 동안 같은 체크아웃에서 pytest를 겹쳐 돌려도 아무것도 알리지 않는다

**상태:** 열림
**어디로:** `.claude/rules/tools.md`의 `hook_edit_during_mutate` 항목과 `tools/`의 훅(`tools/mutate.py`의 표지를 읽어 그 pid가 살아 있는 체크아웃에서 `pytest`를 도는 Bash 호출을 알리거나 막는다. `mutate-marker-discovery`와 같은 도구를 다루지만 처방이 달라 따로 둔다)
**승인:** 자체 승인 2026-11-14, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-14-1128-search-eval-03-eval-index-command.md, ADR 불필요

`tools/mutate.py`는 변이를 돌리는 동안 소스를 잠깐 바꿔 두므로, 그사이에 같은 체크아웃에서 도는 pytest는 변이가 들어간 소스를 시험한다. 03 세션은 변이 표를 돌리면서 pytest를 겹쳐 돌려, 겹친 구간의 결과를 버리고 다시 돌았다. 편집은 `hook_edit_during_mutate`가 알리지만 pytest 실행은 알리는 장치가 없고, `tools/mutate.py`에도 겹침을 막는 코드가 없다. 잃은 것은 시간이고 데이터는 아니다. 처방은 편집용 훅이 쓰는 표지를 그대로 읽어 pytest 호출에도 알리는 것이다. 변이 도구끼리 겹치는 사건은 `mutate-concurrent-runs`가 따로 센다.
