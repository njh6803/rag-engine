"""Qdrant v1.20.0 태그의 charabia 피처와 qdrant-client PyPI 메타데이터·py.typed를 확인한다.

보는 것: Qdrant 저장소 `v1.20.0` 태그의 `lib/segment/Cargo.toml` 에서 charabia(다국어 토크나이저)
의존 줄과 `[features]` 의 multiling 피처(한국어 전문 검색이 기본 빌드에 드는지, ADR 0006·비교 문서),
qdrant-client 의 최신 판·라이선스·requires_python·의존성, 휠 크기와 `py.typed` 유무.

실행: uv run python -I .scratch/core/probes/facts/qdrant_facts.py
(저장소 루트에서. 표준 라이브러리만 쓴다. GitHub raw, PyPI 를 부르고 휠 하나를 메모리로 받는다.)

2026-11-09에 돌려 표준 출력으로 읽었다. 첫 실행은 charabia 줄의 첫 줄만 찍어(피처 목록이 여러
줄이다) 태그의 피처를 보여 주지 못했고, 출력 파일도 남기지 않았다. qdrant-client 의 판은 같은 날
받은 `vector-store/wheel_pytyped.txt` 가 1.20.0 으로 적고 있다.

저장소로 옮기며(2026-11-09) charabia 의존 줄을 `{ … }` 블록 전체로 찍게 고치고 다시 돌렸다. 출력은
`qdrant_facts_out.txt`. v1.20.0 태그의 charabia 0.10.0 피처는 greek, hebrew, thai,
chinese-segmentation, chinese-normalization 다섯이고(`korean` 없음), `[features]` 에는 multiling·
charabia 줄이 없다. 그 밖의 코드는 그대로다.
"""

from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile

CARGO = "https://raw.githubusercontent.com/qdrant/qdrant/v1.20.0/lib/segment/Cargo.toml"
with urllib.request.urlopen(CARGO, timeout=30) as resp:
    cargo = resp.read().decode()
dep = re.search(r"^charabia\s*=\s*\{.*?\}\s*$", cargo, re.S | re.M)
if dep:
    for line in dep.group(0).splitlines():
        print("Cargo v1.20.0:", line.strip())
else:
    print("Cargo v1.20.0: charabia 의존 줄 없음")
features = re.search(r"\[features\](.*?)(\n\[|\Z)", cargo, re.S)
if features:
    for line in features.group(1).splitlines():
        if "multiling" in line or "charabia" in line:
            print("features:", line.strip())

with urllib.request.urlopen("https://pypi.org/pypi/qdrant-client/json", timeout=30) as resp:
    meta = json.load(resp)
info = meta["info"]
print("qdrant-client", info["version"], info.get("license_expression") or info.get("license"))
print("requires_python", info["requires_python"])
deps: list[str] = info.get("requires_dist") or []
for dep in deps:
    print("  dep:", dep)
wheel_url = next(u["url"] for u in meta["urls"] if u["filename"].endswith(".whl"))
with urllib.request.urlopen(wheel_url, timeout=60) as resp:
    blob = resp.read()
names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
print(
    "wheel MB", round(len(blob) / 1e6, 2), "py.typed:", [n for n in names if n.endswith("py.typed")]
)
