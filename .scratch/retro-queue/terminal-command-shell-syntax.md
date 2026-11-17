# terminal-command-shell-syntax: 사용자 터미널에서 칠 명령을 bash 문법으로 안내해 PowerShell에서 실패했다

**상태:** 열림
**어디로:** `CLAUDE.md` 환경 함정 절에 한 줄(사용자 터미널에 넘기는 명령은 개발 기계의 셸인 PowerShell 문법으로 쓴다). 더하는 것이라 다섯 번째에 반영한다
**승인:** 자체 승인 2026-11-17, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-17-1101-search-eval-13-first-judge-run.md, ADR 불필요

티켓 13에서 사용자가 자기 PowerShell에서 `judge`를 돌려야 했다. 이 세션이 환경 변수를 bash의 `export`로 안내했고 사용자의 PowerShell이 "`export`는 cmdlet, 함수, 스크립트 파일 또는 실행 프로그램의 이름으로 인식되지 않는다"는 오류를 냈다. 다시 `$env:` 문법과 `Measure-Command`로 안내해 풀었다. 손상은 없고 사용자가 한 번 더 붙여 넣는 비용이 들었다.
