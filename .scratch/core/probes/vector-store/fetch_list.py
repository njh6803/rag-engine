"""목록 파일("이름 URL" 한 줄씩, # 주석 허용)의 원문을 내려받는다. fetch_raw5.py의 보충(실패분과
추가 원문).

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/fetch_list.py \\
    <dl-dir> <items-file>
(표준 라이브러리만 쓴다. 목록 파일은 같은 폴더의 `items6.txt`~`items9.txt`.)

2026-11-09에 items6·items7 로 돌린 상태 출력이 같은 폴더의 `fetch_list6.txt`·`fetch_list7.txt`다
(items8·items9 의 출력은 남기지 않았다). 내려받은 원문(dl2/)은 저장소 밖이라 옮기지 않았다.
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
items = []
for line in pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name, url = line.split(None, 1)
    items.append((name, url))


def get(item):
    name, url = item
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; curl/8)", "Accept": "*/*"}
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        (out / name).write_bytes(data)
        return f"OK   {len(data):>8}  {name}"
    except Exception as e:
        return f"FAIL {str(e)[:40]:>8}  {name}  <- {url}"


with concurrent.futures.ThreadPoolExecutor(8) as ex:
    for line in ex.map(get, items):
        print(line)
