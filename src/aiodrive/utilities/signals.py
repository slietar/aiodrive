import asyncio
import contextlib
import signal
from collections.abc import Collection


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


async def wait_for_signal(sig_names: Collection[str], /):
    loop = asyncio.get_event_loop()
    future = asyncio.Future()

    def handler():
        future.set_result(None)

    for signame in sig_names:
        loop.add_signal_handler(getattr(signal, signame), handler)

    try:
        await future
    finally:
        for signame in sig_names:
            loop.remove_signal_handler(getattr(signal, signame))
