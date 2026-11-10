"""작업자 조립(`run_once_with_settings`, 티켓 07). 작업자는 서버 없이 따로 돌 수 있으므로 조립이
로깅을 직접 설정한다."""

import logging
from collections.abc import Callable

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.adapters.settings import Settings
from rag_engine.worker.assembly import run_once_with_settings


async def test_조립이_설정의_형식으로_로깅을_설정한다(
    seeded_database_url: str, make_settings: Callable[..., Settings]
) -> None:
    root = logging.getLogger()
    root.handlers[:] = []

    processed = await run_once_with_settings(make_settings(seeded_database_url))

    assert [processed, [type(h.formatter) for h in root.handlers]] == [0, [JsonLinesFormatter]]
