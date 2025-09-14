import asyncio
from collections.abc import AsyncIterable
from time import time


async def repeat_periodically(min_interval: float, /) -> AsyncIterable[None]:
    """
    Create an iterable that yields periodically.

    The first iteration happens immediately.

    Parameters
    ----------
    min_interval
        The minimum interval between yields, in seconds.

    Yields
    ------
    None
    """

    while True:
        last_yield_time = time()
        yield
        wait_time = min_interval - (time() - last_yield_time)

        if wait_time > 0:
            await asyncio.sleep(wait_time)


__all__ = [
    'repeat_periodically',
]
