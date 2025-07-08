import asyncio
from collections.abc import Callable
from threading import Event
from typing import Concatenate


class ThreadTerminatedException(BaseException):
    pass

type ThreadCheckpointFunc = Callable[[], None]

async def to_thread_with_checkpoint[**P, T](func: Callable[Concatenate[ThreadCheckpointFunc, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
    cancelled_event = Event()

    def checkpoint():
        if cancelled_event.is_set():
            raise ThreadTerminatedException

    def thread_main():
        return func(checkpoint, *args, **kwargs)

    task = asyncio.create_task(asyncio.to_thread(thread_main))

    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        cancelled_event.set()

        try:
            await task
        except* ThreadTerminatedException:
            pass

        raise
    else:
        return await task


async def to_thread_patient[**P, T](func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    def inner_func(_checkpoint: ThreadCheckpointFunc, *args: P.args, **kwargs: P.kwargs) -> T:
        return func(*args, **kwargs)

    return await to_thread_with_checkpoint(inner_func, *args, **kwargs)
