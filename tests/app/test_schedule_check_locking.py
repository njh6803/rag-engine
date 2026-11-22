"""원천 행 잠금이 일정 확인과 다른 요청 사이에서 하는 일(source-sync 티켓 10, 명세 "일정과 일정
확인").

일정 확인과 일정을 고치는 요청은 원천 행을 `FOR NO KEY UPDATE`로 잡아 서로 기다린다. 그러나 지금
동기화가 작업 행과 기록 행을 넣을 때 외래 키 확인이 거는 `FOR KEY SHARE`와는 부딪치지 않는다.
`FOR UPDATE`였다면 그 요청이 일정 확인의 커밋까지 기다리고, 같은 원천에 일정 확인이 작업을 넣으려
할 때 서로를 기다리는 교착이 난다.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.support.schedule_sources import CHECK_TIME, add_scheduled_source, sync_jobs

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.identifiers import new_id

# 잠금이 풀릴 때까지 기다리는 쪽이 기다리고 있음을 확인하는 짧은 시간이다.
STILL_WAITING = 0.5
# 기다릴 이유가 없는 쪽이 끝나기를 기다리는 상한이다. 정상일 때는 수십 밀리초에 끝난다.
GENEROUS = 20.0


async def test_일정_확인이_원천_행을_잡은_동안에도_지금_동기화_요청은_기다리지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "docs", next_run_at=CHECK_TIME)

    async with unit_of_work.begin() as checking:
        locked = await checking.catalog.lock_due_sources(CHECK_TIME)
        assert [item.id for item in locked] == [source.id]

        requested = await asyncio.wait_for(
            request_sync(
                unit_of_work,
                "docs",
                apply_empty=False,
                reread=False,
                request_id=new_id(),
                now=CHECK_TIME,
            ),
            GENEROUS,
        )

    assert [job.id for job in await sync_jobs(engine, source)] == [requested.job_id]


async def test_원천_행을_잠그고_읽는_쪽은_다른_연결이_잡은_잠금이_풀릴_때까지_기다린다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "docs", next_run_at=CHECK_TIME)

    async with unit_of_work.begin() as holder:
        assert await holder.catalog.lock_source(source.id) is not None

        async def lock_in_another_connection() -> None:
            async with unit_of_work.begin() as waiter:
                await waiter.catalog.lock_source(source.id)

        waiting = asyncio.create_task(lock_in_another_connection())
        done, _ = await asyncio.wait({waiting}, timeout=STILL_WAITING)
        assert not done

    await asyncio.wait_for(waiting, GENEROUS)
