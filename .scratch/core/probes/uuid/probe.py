"""UUIDv7 식별자 라이브러리 둘(uuid6, uuid-utils)을 소비 지점까지 대 보는 프로브(ADR 0015, 명세).

ADR 0015 는 "uuid6 MIT 또는 uuid-utils BSD, py.typed 를 보고 명세가 하나를 고른다"고 했다. py.typed
는 둘 다 있어(`db-queue/report_q4q5q6.txt`) 그것으로는 갈리지 않으므로, 이 프로브는 생성한 값이 표준
라이브러리 `uuid.UUID` 로 그대로 쓰이는지(SQLAlchemy `Uuid` 타입과 pydantic `UUID` 칸의 소비 지점),
같은 밀리초 안에서 단조 증가하는지, 순수 파이썬인지(폐쇄망 반입과 플랫폼 휠)를 본다.

실행(저장소 루트에서):
    uv run --with uuid6==2025.0.1 --with uuid-utils==1.2.0 python -I -X utf8
    .scratch/core/probes/uuid/probe.py
타입 검사: 저장소 설정의 기본 exclude(`**/.*`)가 `.scratch` 를 건너뛰므로 exclude 를 비운 임시
pyrightconfig 로
`uv run --with uuid6==2025.0.1 --with uuid-utils==1.2.0 pyright -p <설정> <이 폴더>` 를
돌린다(프로브 README 의 방법). 출력 `probe_out.txt`, `pyright_out.json`.

2026-11-10 에 돌렸다. 결과 요약은 `probe_out.txt` 와 프로브 README 의 행에 있다.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
import time
import uuid

import uuid6
import uuid_utils


def is_pure_python(package: str) -> bool:
    files = importlib.metadata.files(package) or []
    return not any(f.suffix in {".pyd", ".so", ".dll"} for f in files)


def consume_stdlib(value: uuid.UUID) -> str:
    """소비 지점: 표준 라이브러리 UUID 를 받는 자리(SQLAlchemy Uuid 바인딩, pydantic UUID 칸의
    모양)."""
    return str(value)


def main() -> None:
    print("python", sys.version.split()[0])
    for pkg in ("uuid6", "uuid-utils"):
        print(
            pkg, importlib.metadata.version(pkg), "pure_python" if is_pure_python(pkg) else "binary"
        )

    a = uuid6.uuid7()
    print("uuid6.uuid7 ->", type(a).__module__, type(a).__name__, "version", a.version)
    print("  uuid.UUID in mro:", uuid.UUID in type(a).__mro__)
    print("  stdlib consumer:", consume_stdlib(a))

    b = uuid_utils.uuid7()
    print("uuid_utils.uuid7 ->", type(b).__module__, type(b).__name__, "version", b.version)
    print("  uuid.UUID in mro:", uuid.UUID in type(b).__mro__)
    compat_spec = importlib.util.find_spec("uuid_utils.compat")
    print("  uuid_utils.compat present:", compat_spec is not None)

    # 같은 밀리초 안의 단조 증가(정렬 가능성). 10만 개를 연속으로 만든다.
    for name, make in (("uuid6", uuid6.uuid7), ("uuid_utils", uuid_utils.uuid7)):
        t0 = time.perf_counter()
        prev = make()
        ordered = True
        for _ in range(100_000):
            cur = make()
            if cur.int <= prev.int:
                ordered = False
            prev = cur
        dt = time.perf_counter() - t0
        print(f"{name}: 100k monotonic={ordered} elapsed={dt:.3f}s")


if __name__ == "__main__":
    main()
