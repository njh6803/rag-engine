# python-i-utf8: `python -I`는 `PYTHONUTF8` 같은 PYTHON* 환경 변수를 읽지 않아 Windows에서 출력이 cp949로 깨진다

**상태:** 닫힘 (`.scratch/harness/issues/env-traps-crlf-and-utf8.md`, 2026-11-21, `CLAUDE.md` 환경 함정에 `uv run python -I -X utf8 <파일>` 한 줄을 더했다)
**어디로:** `CLAUDE.md` 환경 함정 절의 한 줄(`uv run python -I` 뒤에 `-X utf8`을 붙인다)
**승인:** 자체 승인 2026-11-09, 5회차(더하는 것이라 다섯 번째에 반영한다. 5회차에 이르러 chore 배치 조건이다), 일지 2026-11-09-2125-core-design.md, 2026-11-10-0118-core-spec.md, 2026-11-12-1833-dev-review-bot-off.md, 2026-11-14-2147-search-eval-12-relevance-judge-claude.md(4회차: 사용자가 자기 터미널에서 돌린 프로브의 출력을 파일로 받았더니 cp949였다. `-I`는 아니지만 윈도 Python이 로케일 인코딩으로 쓰는 같은 뿌리라 센다), 2026-11-16-0100-search-eval-11-fast-gate-ci.md(5회차: 티켓 11의 앞 세션이 CI 실행 기록을 읽는 스크립트를 `python -I`로 돌렸더니 `PYTHONUTF8`이 무시돼 출력이 깨졌고 `-X utf8`로 풀었다), 2026-11-18-2135-release-image-tickets.md(6회차), 2026-11-19-1044-glossary-contract-version-names.md(7회차: 옛 이름을 훑는 스크립트를 `uv run python`으로 돌렸더니 한글 출력에서 cp949 `UnicodeEncodeError`가 났고 `-I -X utf8`로 풀었다), ADR 불필요

설계 인터뷰 일지의 인용을 뽑는 스크립트를 `PYTHONUTF8=1 uv run python -I …`로 돌렸더니 한글이 깨져 나왔다. `-I`가 환경 변수를 무시해서이고, `-X utf8`로 풀었다. 큰 출력은 파일로 리다이렉트해 Read로 읽었다.
