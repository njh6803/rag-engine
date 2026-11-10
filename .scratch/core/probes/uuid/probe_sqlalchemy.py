"""uuid6 가 만든 UUIDv7 값이 pydantic `uuid.UUID` 칸과 SQLAlchemy 2.1 Core 의 `sa.Uuid` 열(psycopg 3
비동기, PostgreSQL 18)에 변환 없이 드는지 잰다.

근거로 드는 곳은 명세(`.scratch/core/spec.md`)의 데이터 모델 절(UUIDv7 라이브러리)이다. `probe.py`
는 MRO 와 `str()` 만 봐서, 명세가 SQLAlchemy·pydantic 수용을 첫 구현 티켓에 미뤄 두었다. 2026-11-10
티켓 세션의 spec-reviewer 가 세션 스크래치패드에서 돌린 임시 스크립트의 H 부분을 옮겼다(독스트링과
서식만 고쳤다. G 부분은 `pg-ddl/drop_concurrently.py`). 셀프 리뷰가 uuid6 의 클래스 이름도 `UUID` 라
클래스 이름으로는 보존을 가르지 못한다고 짚어, 모듈과 `is`, 네 패키지의 판을 찍게 고쳤다. 보는 것
셋. isinstance, pydantic 의 JSON 직렬화와 보존되는 타입, 비동기 엔진으로 넣고 읽은 값이 같은지.

실행(저장소 루트에서. `pg-ddl/ddl_locks.py` 독스트링의 컨테이너가 떠 있어야 한다). Windows 에서
`uv run --with` 가 greenlet 휠에서 실패해(ADR 0011 이 적은 우회와 같다) 임시 가상환경을 쓴다:
    uv venv <폴더>/venv_h
    uv pip install -p <폴더>/venv_h "sqlalchemy[asyncio]==2.1.8" "psycopg[binary]==3.3.8" \
        pydantic==2.14.3 uuid6==2025.0.1
    <폴더>/venv_h/Scripts/python -I -X utf8 .scratch/core/probes/uuid/probe_sqlalchemy.py \
        postgresql://postgres:probe@127.0.0.1:55432/postgres
`<폴더>` 는 저장소 밖(세션 스크래치패드)이다. 출력은 `probe_sqlalchemy_out.txt`(2026-11-10)다.
"""

import asyncio
import sys
import uuid
from importlib.metadata import version

import pydantic
import sqlalchemy as sa
import uuid6
from sqlalchemy.ext.asyncio import create_async_engine

DSN = sys.argv[1]


class M(pydantic.BaseModel):
    id: uuid.UUID


async def part_h() -> None:
    v = uuid6.uuid7()
    print("H: isinstance uuid.UUID:", isinstance(v, uuid.UUID))
    m = M(id=v)
    kept = type(m.id)
    print(
        "H: pydantic json:", m.model_dump_json(), "kept:", f"{kept.__module__}.{kept.__qualname__}"
    )
    print(
        "H: pydantic kept the same object:",
        m.id is v,
        "uuid6 type:",
        f"{type(v).__module__}.{type(v).__qualname__}",
    )
    url = DSN.replace("postgresql://", "postgresql+psycopg://")
    eng = create_async_engine(url, hide_parameters=True)
    md = sa.MetaData()
    t = sa.Table("uu", md, sa.Column("id", sa.Uuid, primary_key=True))
    async with eng.begin() as conn:
        await conn.run_sync(md.drop_all)
        await conn.run_sync(md.create_all)
        await conn.execute(t.insert().values(id=v))
        got = (await conn.execute(sa.select(t.c.id))).scalar_one()
        read = type(got)
        print(
            "H: sqlalchemy round trip equal:",
            got == v,
            "read type:",
            f"{read.__module__}.{read.__qualname__}",
        )
    await eng.dispose()
    names = ("sqlalchemy", "psycopg", "pydantic", "uuid6")
    print("H: versions", " ".join(f"{n} {version(n)}" for n in names))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(part_h())
