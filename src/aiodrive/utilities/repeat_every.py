import asyncio
from collections.abc import AsyncIterable
from time import time


async def repeat_every(min_interval: int, /) -> AsyncIterable[None]:
    while True:
        last_yield_time = time()
        yield
        wait_time = min_interval - (time() - last_yield_time)

        if wait_time > 0:
            await asyncio.sleep(wait_time)
