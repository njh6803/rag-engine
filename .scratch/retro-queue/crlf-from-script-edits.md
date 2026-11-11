# crlf-from-script-edits: 스크래치 파이썬의 `write_text`와 stdout 리다이렉트가 Windows에서 저장소 파일 아홉을 CRLF로 바꿨고 `check_line_separators`는 설계상 CRLF를 보지 않는다

**상태:** 열림
**어디로:** `tools/check_line_separators.py`(`.gitattributes`가 `* text=auto eol=lf`인 저장소에서 CRLF를 어긋남으로 낸다. 독스트링이 CRLF를 보지 않는다고 적은 설계를 바꾸는 것이라 못 보는 것과 `tests/tools/`의 시험을 같이 고친다) 또는 `CLAUDE.md` 환경 함정 한 줄(저장소 파일을 스크립트로 쓸 때 `newline` 인자를 LF로 주거나 바이트로 쓴다. 검사 층이 더 높다)
**승인:** 자체 승인 2026-11-10, 3회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-10-0118-core-spec.md, 2026-11-11-0615-core-07-first-search-round-trip.md, 2026-11-11-1328-core-08-parsers-isolation.md, ADR 불필요

명세 세션이 Bash heredoc의 `uv run python`으로 명세·일지·README·프로브를 고치며 `pathlib.Path.write_text`를 썼고 프로브 출력은 `>`로 받았다. Windows의 텍스트 모드가 LF를 CRLF로 바꿔 아홉 파일이 CRLF가 됐고, 손으로 친 `check_line_separators`는 0이었으며 `git add`의 `CRLF will be replaced by LF` 경고로야 알았다. 바이트 치환으로 LF로 되돌렸다. 커밋은 git이 정규화해 손상은 없었다.
