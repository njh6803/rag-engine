"""멈춘 자식 시험(`tests/adapters/test_parse_runner.py`의 `test_메시지를_보내다_멈춘_자식이_…`)의
윈도 기대(`parse_failed`)가 자식의 기동 시간과 기한(`timeout_seconds`)의 경쟁인지 잰다.

두 방식이 있다.
- `one <기한>`: `StallingMidMessageParser`를 실제 러너에 한 번 태워 `<기한> <오류 코드> <소요>`를 한
  줄로 낸다. 기한을 길게(30초) 주면 소요가 자식이 첫 메시지를 보내기까지 걸린 시간이다.
- `sweep <동시 수>`: 기한 2초와 10초로 `one`을 그 수만큼 동시에 띄워 코드별 개수와 최대 소요를 센다.

실행(저장소 루트, 경로는 `STALL=.scratch/harness/probes/parse_runner_stall_deadline`):
`PYTHONPATH=. uv run python $STALL/stall_boot_race.py sweep 16`

무거운 import는 함수 안에서 한다. spawn 자식이 이 파일을 다시 읽으므로, 맨 위에서 하면 자식의
기동이 길어져 재는 값이 달라진다.
"""

import asyncio
import subprocess
import sys
import time
from collections import Counter

_DEADLINES = (2, 10)


async def _one(deadline: int) -> str:
    from tests.support.fake_parsers import FAKE_MIME

    from rag_engine.adapters.parsers.registry import (
        ParserRegistry,
        ParserSpec,
        discover_parser_specs,
    )
    from rag_engine.adapters.parsers.runner import SubprocessParseRunner
    from rag_engine.domain.errors import PermanentFailure

    fake = ParserSpec(
        name="fake",
        target="tests.support.fake_parsers:StallingMidMessageParser",
        library="fake-lib",
    )
    runner = SubprocessParseRunner(
        ParserRegistry([fake, *discover_parser_specs()]),
        timeout_seconds=deadline,
        memory_mb=2048,
        max_pages=1000,
        max_text_mb=64,
        max_unzipped_mb=512,
        max_compression_ratio=100,
    )
    started = time.monotonic()
    try:
        await runner.parse(b"x", FAKE_MIME)
        code = "ok"
    except PermanentFailure as error:
        code = error.code.value
    return f"{deadline} {code} {time.monotonic() - started:.2f}"


def _sweep(parallel: int) -> None:
    for deadline in _DEADLINES:
        children = [
            subprocess.Popen(
                [sys.executable, __file__, "one", str(deadline)],
                stdout=subprocess.PIPE,
                text=True,
            )
            for _ in range(parallel)
        ]
        lines = [(child.communicate()[0] or "").strip().split() for child in children]
        codes = Counter(line[1] for line in lines if len(line) == 3)
        slowest = max((float(line[2]) for line in lines if len(line) == 3), default=0.0)
        print(f"기한 {deadline}초, 동시 {parallel}개: {dict(codes)}, 최대 소요 {slowest:.2f}초")


if __name__ == "__main__":
    if sys.argv[1] == "one":
        print(asyncio.run(_one(int(sys.argv[2]))))
    else:
        _sweep(int(sys.argv[2]))
