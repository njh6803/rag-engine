"""내려받은 wheel 들에서 라이선스 파일의 머리(첫 12줄)와 METADATA 의 Requires-Dist 를 뽑고,
wheel 을 <extract_dir>/<pkg>/ 아래에 풀어 둔다(이후 grep 용).

사용: uv run python -I .scratch/core/probes/parsers/wheel_inspect.py <download_dir> <extract_dir>
(저장소 루트에서. 표준 라이브러리만 쓴다. <download_dir>은 pypi_probe.py 가 휠을 내려받은 곳.)

2026-11-09에 pypi_probe.py 가 받은 휠에 돌려 표준 출력으로 읽었다. 출력 파일은 남기지 않았고 휠과
푼 디렉터리도 옮기지 않았다. 같은 이름의 `db-queue/wheel_inspect.py`는 다른 스크립트다.
"""

import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
dl_dir = Path(sys.argv[1])
ex_dir = Path(sys.argv[2])
ex_dir.mkdir(parents=True, exist_ok=True)

for whl in sorted(dl_dir.glob("*.whl")):
    print("#####", whl.name)
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        for n in names:
            up = n.upper()
            if ("LICEN" in up or "COPYING" in up or "NOTICE" in up) and not n.endswith("/"):
                if "BUILD_LICENSES" in n:
                    continue
                text = z.read(n).decode("utf-8", "replace")
                lines = [ln for ln in text.splitlines() if ln.strip()]
                print("---", n, f"({len(text)} chars)")
                for ln in lines[:12]:
                    print("   |", ln[:160])
        meta = [n for n in names if n.endswith(".dist-info/METADATA")]
        if meta:
            text = z.read(meta[0]).decode("utf-8", "replace")
            reqs = [ln for ln in text.splitlines() if ln.startswith("Requires-Dist")]
            print("--- Requires-Dist:", len(reqs))
            for r in reqs[:40]:
                print("   |", r)
        target = ex_dir / whl.name.split("-")[0]
        if not target.exists():
            z.extractall(target)
    print()
