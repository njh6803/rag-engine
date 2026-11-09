# uv-with-windows-lock: `uv run --with <패키지>`가 Windows에서 greenlet 휠의 `.data` 디렉터리 잠금(os error 32)으로 실패한다

**상태:** 열림
**어디로:** `CLAUDE.md` 환경 함정 절의 한 줄(저장소 밖 패키지를 임시로 얹는 프로브는 `uv venv` + `uv pip install`로 만든 임시 가상환경의 python으로 돌리고, 독스트링에 그 길을 적는다)
**승인:** 자체 승인 2026-11-09, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-09-2125-core-design.md, ADR 불필요

`.scratch/core/probes/sqlalchemy-async/probe.py`를 `uv run --with "sqlalchemy[asyncio]" --with "psycopg[binary]" --with pgvector --with alembic python …`으로 두 번 돌렸고 두 번 다 os error 32로 끝났다. 임시 가상환경을 만들어 그 python으로 돌리고 pyright에는 `--pythonpath`로 넘겼다(그 독스트링).
