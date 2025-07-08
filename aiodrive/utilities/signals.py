import asyncio
import contextlib
import signal
import threading
from collections.abc import Callable, Collection
from typing import Concatenate


@contextlib.asynccontextmanager
async def handle_signals(sig_names: Collection[str], /):
    loop = asyncio.get_event_loop()

    task = asyncio.current_task()
    assert task is not None

    for signame in sig_names:
        loop.add_signal_handler(getattr(signal, signame), task.cancel)

    try:
        yield
    except asyncio.CancelledError:
        if task.cancelling() == 0:
            raise
    finally:
        for signame in sig_names:
            loop.remove_signal_handler(getattr(signal, signame))



class ThreadTerminatedException(BaseException):
    pass

type ThreadCheckpointFunc = Callable[[], None]

async def to_thread_with_checkpoint[**P, T](func: Callable[Concatenate[ThreadCheckpointFunc, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
    cancelled_event = threading.Event()

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
