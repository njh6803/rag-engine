# commit-msg-after-slow-checks: 커밋 메시지 타입 검사가 8분 걸리는 검사 러너 뒤에 돌아, 허용되지 않은 타입이 8분을 쓰고서야 막힌다

**상태:** 열림
**어디로:** `tools/` 의 PreToolUse 훅 하나(`git commit -m`의 제목 타입을 `tools/check_commit_msg.py`로 먼저 본다. 판정은 같은 모듈을 부른다)
**승인:** 자체 승인 2026-11-12, 3회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-12-1833-dev-review-bot-off.md, 2026-11-13-1324-code-review-transition-crossing.md, 2026-11-14-1438-search-eval-04-fast-run-report.md가 3회차다(제목이 80자로 72자 제한을 넘어 `pytest` 468초를 돈 뒤에야 막혔다. 명령은 `git commit -F <메시지 파일>`이었고 `hook_bash_commit_msg`가 있는데도 먼저 막지 못했다. 명령이 `cd <워크트리> &&`로 시작하는 복합 명령이었고 세션의 작업 폴더가 연결된 워크트리였다. 훅이 왜 지나갔는지는 진단하지 않았다), ADR 불필요

`ci:` 타입으로 커밋했더니 pre-commit의 `parallel-checks`가 480초를 돈 뒤에야 `commit-msg` 훅(`.pre-commit-config.yaml`의 `commit-msg` 단계)이 "타입은 feat, fix, docs, style, refactor, test, chore, perf"라며 막았다. `commit-msg` 단계는 `pre-commit` 단계 뒤에 도는 것이 pre-commit의 순서라 훅 설정만으로 앞당길 수 없다. 메시지는 `-m`에 이미 있어 명령을 칠 때 값싸게 볼 수 있다.
