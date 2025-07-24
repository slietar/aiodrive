import asyncio
import contextlib
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from typing import Optional

from .iterator import ensure_aiter


# TODO: Add option to output results in the order of the input iterable.

@contextlib.asynccontextmanager
async def map_parallel[T, S](
    iterable: AsyncIterable[T] | Iterable[T],
    mapper: Callable[[T], Awaitable[S]],
    /, *,
    max_concurrent_count: Optional[int] = None,
):
    queue = asyncio.Queue[S]()
    event = asyncio.Event()

    closed = False
    running_count = 0
    iterator = ensure_aiter(iterable)

    async def run(item: T):
        nonlocal running_count

        try:
            queue.put_nowait(await mapper(item))
        finally:
            running_count -= 1

        event.set()

    async def put_queue():
        nonlocal closed, running_count

        while True:
            while (max_concurrent_count is None) or (running_count < max_concurrent_count):
                try:
                    item = await anext(iterator)
                except StopAsyncIteration:
                    closed = True
                    return
                else:
                    group.create_task(run(item))
                    running_count += 1

            event.clear()
            await event.wait()

    async with asyncio.TaskGroup() as group:
        group.create_task(put_queue())

        async def create_iter():
            while (not closed) or (running_count > 0) or not queue.empty():
                yield await queue.get()

        yield create_iter()
