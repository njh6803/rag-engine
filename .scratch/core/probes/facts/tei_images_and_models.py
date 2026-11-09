"""TEI CPU 이미지, Ollama·vLLM 이미지의 amd64 압축 크기, TEI README 의 Qwen3·rerank 줄, TEI 라우터
소스의 `auto_truncate` 기본값을 받는다.

보는 것: GHCR 의 `huggingface/text-embeddings-inference:cpu-1.9.4` 매니페스트 레이어 합(amd64,
압축 크기 MB = 바이트/1e6), Docker Hub 의 `ollama/ollama` 와 `vllm/vllm-openai` 태그의 amd64 압축
크기, TEI 저장소 v1.9.4 태그 README 에서 `qwen3`·`rerank` 가 든 줄, 같은 태그의
`router/src/main.rs` 에서 `auto_truncate` 인자 선언과 그 앞 일곱 줄(clap 기본값),
`router/src/http/server.rs` 에서 `/v1/embeddings` 경로 선언과 `info.auto_truncate` 를 읽는 줄.
임베딩·리랭커를 TEI 컨테이너에 맡기는 결정(ADR 0010)의 Considered Options 가 드는 수,
"Qwen3-Reranker 는 TEI 가 지원하지 않는다" 와 "상한을 넘는 입력은 거부가 아니라 조용히 잘린다" 의
근거다.

실행: uv run python -I -X utf8 .scratch/core/probes/facts/tei_images_and_models.py
(저장소 루트에서. 표준 라이브러리만 쓴다. ghcr.io, hub.docker.com, raw.githubusercontent.com 을
부른다. 이미지를 내려받지 않는다.)

2026-11-09 셀프 리뷰(명세 축)가 ADR 0010 의 239MB·9.74GB·3.39GB 와 Qwen3-Reranker 문장에 근거
표시가 없다고 짚고, 표준 축이 "거부한다" 가 TEI 소스와 다르다고 짚어 썼다. 출력은
`tei_images_and_models_out.txt`. vLLM 의 9.74GB 는 어느 태그인지 남지 않아 태그를 밝힌 실측으로
바꿨다.
"""

import json
import urllib.parse
import urllib.request

ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def get_json(url: str, headers: dict[str, str] | None = None):  # noqa: ANN201  json 값
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8")


def ghcr_amd64_size(repo: str, tag: str) -> None:
    scope = urllib.parse.quote(f"repository:{repo}:pull", safe="")
    token = get_json(f"https://ghcr.io/token?scope={scope}")["token"]
    headers = {"Authorization": f"Bearer {token}", "Accept": ACCEPT}
    base = f"https://ghcr.io/v2/{repo}/manifests/"
    manifest = get_json(base + tag, headers)
    if "manifests" in manifest:
        picked = next(
            m
            for m in manifest["manifests"]
            if m["platform"]["os"] == "linux" and m["platform"]["architecture"] == "amd64"
        )
        manifest = get_json(base + picked["digest"], headers)
    total = sum(layer["size"] for layer in manifest["layers"])
    print(f"ghcr.io/{repo}:{tag} amd64 layers {len(manifest['layers'])} MB {total / 1e6:.1f}")


def hub_tags(repo: str, count: int, name: str) -> None:
    """Docker Hub 에서 이름에 `name` 이 든 최근 태그 `count` 개의 amd64 압축 크기."""
    query = f"page_size={count}&ordering=last_updated&name={name}"
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?{query}"
    for tag in get_json(url)["results"]:
        for image in tag["images"]:
            if image["architecture"] == "amd64" and image["os"] == "linux":
                size = image["size"] / 1e6
                print(f"{repo}:{tag['name']} amd64 MB {size:.1f} {tag['last_updated']}")


def source_lines(repo: str, tag: str, path: str, needle: str, before: int = 0) -> None:
    """GitHub 저장소 `tag` 의 파일에서 `needle` 이 든 줄(대소문자 무시)과 그 앞 `before` 줄."""
    lines = get_text(f"https://raw.githubusercontent.com/{repo}/{tag}/{path}").splitlines()
    for index, line in enumerate(lines):
        if needle.lower() in line.lower():
            for number in range(max(0, index - before), index + 1):
                print(f"{path} {tag} L{number + 1}: {lines[number].strip()}")


TEI = "huggingface/text-embeddings-inference"
ghcr_amd64_size(TEI, "cpu-1.9.4")
hub_tags("ollama/ollama", 2, "latest")
hub_tags("vllm/vllm-openai", 2, "latest")
hub_tags("vllm/vllm-openai", 3, "v0.3")
source_lines(TEI, "v1.9.4", "README.md", "qwen3")
source_lines(TEI, "v1.9.4", "README.md", "rerank")
source_lines(TEI, "v1.9.4", "router/src/main.rs", "auto_truncate: bool", before=7)
source_lines(TEI, "v1.9.4", "router/src/http/server.rs", '"/v1/embeddings"')
source_lines(TEI, "v1.9.4", "router/src/http/server.rs", "info.auto_truncate")
