# control-char-from-script-escape: 스크래치 파이썬의 일반 문자열에 Windows 경로를 넣어 `\a`가 BEL(U+0007)이 되었고, 그 문자가 티켓 파일에 들어갔다

**상태:** 열림
**어디로:** `tools/check_line_separators.py`(text 파일에서 탭·LF·CR 밖의 날것 C0 제어 문자와 DEL을 어긋남으로 낸다. 같은 파일에서 CRLF를 보는 일은 `crlf-from-script-edits`가 세니, 반영할 때 한 chore로 묶는다)
**승인:** 자체 승인 2026-11-18, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-18-2135-release-image-tickets.md, ADR 불필요

release-image 티켓 세션이 티켓 일곱에 같은 문구(`git -C C:\project\agent fetch origin`)를 넣는 스크래치 스크립트를 raw가 아닌 문자열로 써서, 티켓 06에 BEL이 들어갔다. 세션이 결과를 보다 스스로 찾아 raw 문자열로 다시 고쳤다. 커밋 전 검사 `check_line_separators`는 BEL을 보지 않는다. 같은 세션이 BEL 한 글자를 넣은 스크래치 `.md`를 그 도구에 넣어 종료 0을, U+2028을 넣은 대조 파일로 종료 1을 손으로 봤다(`uv run python tools/check_line_separators.py <파일>`).
