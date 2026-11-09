"""RabbitMQ 이미지 크기(Docker Hub v2 API, amd64 압축 크기)와 파이썬 클라이언트의 PyPI 메타데이터를
받는다.

보는 것: `library/rabbitmq` 의 `4-management`·`4` 태그 amd64 압축 크기(MB)와
aio-pika·pika·celery·kombu 의 최신 판, 라이선스, requires_python. 작업 대기열을 PostgreSQL 로 직접
구현할지 메시지 브로커를 둘지 견줄 때(ADR 0009) 브로커 쪽의 설치 크기와 클라이언트 사정을 적으려고
썼다.

실행: uv run python -I .scratch/core/probes/facts/rabbitmq_facts.py
(저장소 루트에서. 표준 라이브러리만 쓴다. Docker Hub 와 PyPI 를 부른다.)

2026-11-09에 돌려 표준 출력으로 읽었다. 첫 실행의 출력 파일은 남기지 않았다(수치는 그날의 스냅숏).
옮긴 뒤 같은 날 다시 돌린 출력이 `rabbitmq_facts_out.txt` 다.

저장소로 옮기며(2026-11-09) `# pyright: ignore[...]` 셋을 지웠다(원칙 II). `object` 로 받은 JSON 을
`isinstance(x, dict)` 로 좁히면 pyright 가 `dict[Unknown, Unknown]` 로 읽어 원소마다 Unknown 이
나므로, 좁히기를 `TypeGuard[Mapping[object, object]]`·`TypeGuard[Sequence[object]]` 를 돌려주는
함수 둘로 감쌌다(안에서는 같은 isinstance 를 한다). 크기는 `int(img["size"])` 대신 숫자로 좁혀 같은
식으로 찍는다. 동작은 같다.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping, Sequence
from typing import TypeGuard


def is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    return isinstance(value, dict)


def is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, list)


def get(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        data: object = json.load(resp)
    if not is_mapping(data):
        raise TypeError(url)
    return {str(k): v for k, v in data.items()}


def hub_size(repo: str, tag: str) -> None:
    data = get(f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}")
    images = data.get("images")
    if is_sequence(images):
        for img in images:
            if not is_mapping(img) or img.get("architecture") != "amd64":
                continue
            size = img.get("size")
            if isinstance(size, int | float):
                print(f"{repo}:{tag} amd64 {int(size) / 1e6:.1f}MB")
                return
    print(f"{repo}:{tag} 크기 못 찾음")


def pypi(name: str) -> None:
    data = get(f"https://pypi.org/pypi/{name}/json")
    info = data["info"]
    if is_mapping(info):
        lic = info.get("license_expression") or info.get("license")
        version = info.get("version")
        requires_python = info.get("requires_python")
        print(f"{name} {version} license={lic!r} requires_python={requires_python!r}")


for tag in ("4-management", "4"):
    hub_size("library/rabbitmq", tag)
for pkg in ("aio-pika", "pika", "celery", "kombu"):
    pypi(pkg)
