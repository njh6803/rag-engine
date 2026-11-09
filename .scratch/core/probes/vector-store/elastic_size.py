"""Elastic 레지스트리(docker.elastic.co) v2 API로 elasticsearch 이미지의 압축 크기(레이어 합)를
읽는다.

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/elastic_size.py <tag>
(표준 라이브러리만 쓴다. docker.elastic.co 를 부른다.)

2026-11-09에 돌려 표준 출력으로 읽었다(비교 문서의 Elasticsearch 이미지 크기 칸). 출력 파일은 남기지
않았다.
"""

import json
import sys
import urllib.request

tag = sys.argv[1]
repo = "elasticsearch/elasticsearch"
tok_url = f"https://docker-auth.elastic.co/auth?service=token-service&scope=repository:{repo}:pull"
with urllib.request.urlopen(
    urllib.request.Request(tok_url, headers={"User-Agent": "curl/8"}), timeout=60
) as r:
    token = json.load(r)["token"]
hdr = {
    "Authorization": f"Bearer {token}",
    "User-Agent": "curl/8",
    "Accept": ", ".join(
        [
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        ]
    ),
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
        return json.load(r)


m = get(f"https://docker.elastic.co/v2/{repo}/manifests/{tag}")
if "manifests" in m:
    amd = [x for x in m["manifests"] if x["platform"].get("architecture") == "amd64"][0]
    m = get(f"https://docker.elastic.co/v2/{repo}/manifests/{amd['digest']}")
total = sum(layer["size"] for layer in m["layers"])
layers = len(m["layers"])
print(f"docker.elastic.co/{repo}:{tag} amd64 compressed_MB={total / 1e6:.1f} layers={layers}")
