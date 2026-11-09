# python-i-utf8: `python -I`는 `PYTHONUTF8` 같은 PYTHON* 환경 변수를 읽지 않아 Windows에서 출력이 cp949로 깨진다

**상태:** 열림
**어디로:** `CLAUDE.md` 환경 함정 절의 한 줄(`uv run python -I` 뒤에 `-X utf8`을 붙인다)
**승인:** 자체 승인 2026-11-09, 2회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-09-2125-core-design.md, 2026-11-10-0118-core-spec.md, ADR 불필요

설계 인터뷰 일지의 인용을 뽑는 스크립트를 `PYTHONUTF8=1 uv run python -I …`로 돌렸더니 한글이 깨져 나왔다. `-I`가 환경 변수를 무시해서이고, `-X utf8`로 풀었다. 큰 출력은 파일로 리다이렉트해 Read로 읽었다.
