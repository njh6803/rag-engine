# commit-msg-after-slow-checks: 커밋 메시지 타입 검사가 8분 걸리는 검사 러너 뒤에 돌아, 허용되지 않은 타입이 8분을 쓰고서야 막힌다

**상태:** 열림
**어디로:** `tools/` 의 PreToolUse 훅 하나(`git commit -m`의 제목 타입을 `tools/check_commit_msg.py`로 먼저 본다. 판정은 같은 모듈을 부른다)
**승인:** 자체 승인 2026-11-12, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-12-1833-dev-review-bot-off.md, ADR 불필요

`ci:` 타입으로 커밋했더니 pre-commit의 `parallel-checks`가 480초를 돈 뒤에야 `commit-msg` 훅(`.pre-commit-config.yaml`의 `commit-msg` 단계)이 "타입은 feat, fix, docs, style, refactor, test, chore, perf"라며 막았다. `commit-msg` 단계는 `pre-commit` 단계 뒤에 도는 것이 pre-commit의 순서라 훅 설정만으로 앞당길 수 없다. 메시지는 `-m`에 이미 있어 명령을 칠 때 값싸게 볼 수 있다.
