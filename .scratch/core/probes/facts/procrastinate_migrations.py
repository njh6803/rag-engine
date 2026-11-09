"""procrastinate 최신 휠 안의 SQL 마이그레이션 파일 수를 센다.

보는 것: PyPI 의 procrastinate 최신 판 휠을 메모리로 받아 `procrastinate/sql/migrations/` 아래
`.sql` 파일의 수와 처음·마지막 이름. 작업 대기열을 PostgreSQL 에 직접 구현하는 결정(ADR 0009)이
procrastinate 를 거른 까닭("자기 마이그레이션을 들여와 우리 alembic 이력과 두 갈래가 된다")의 수를
댄다.

실행: uv run python -I .scratch/core/probes/facts/procrastinate_migrations.py
(저장소 루트에서. 표준 라이브러리만 쓴다. PyPI 를 부르고 휠 하나를 메모리로 받는다.)

2026-11-09 셀프 리뷰(명세 축)가 ADR 0009 의 "마이그레이션 38개" 에 근거 파일이 없다고 짚어 썼다.
출력은 `procrastinate_migrations_out.txt`.
"""

import io
import json
import urllib.request
import zipfile

with urllib.request.urlopen("https://pypi.org/pypi/procrastinate/json", timeout=30) as resp:
    meta = json.load(resp)
version = meta["info"]["version"]
wheel_url = next(u["url"] for u in meta["urls"] if u["filename"].endswith(".whl"))
with urllib.request.urlopen(wheel_url, timeout=60) as resp:
    blob = resp.read()
names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
sql = sorted(n for n in names if "/sql/migrations/" in n and n.endswith(".sql"))
print("procrastinate", version, "wheel MB", round(len(blob) / 1e6, 2))
print("migrations .sql", len(sql))
if sql:
    print("first", sql[0])
    print("last", sql[-1])
