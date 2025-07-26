import asyncio
import contextlib
import signal
from collections.abc import AsyncIterator, Collection


@contextlib.asynccontextmanager
async def handle_signals(sig_names: Collection[str], /) -> AsyncIterator[None]:
    """
    Handle specified signals by cancelling the current task.

    If any of the specified signals is received, the current task is cancelled
    and the signals are no longer listened for. The `asyncio.CancelledError`
    exception is not propagated to the caller unless the current task has been
    cancelled again.

    If the call is cancelled, the signals stop being listened for.

    Parameters
    ----------
    sig_names
        The signal names to handle e.g. `('SIGINT',)`.
    """

    loop = asyncio.get_event_loop()

    task = asyncio.current_task()
    assert task is not None

    # TODO: Improve

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
    """
    Wait for any of the specified signals to be received.

    Parameters
    ----------
    sig_names
        The signal names to wait for e.g. `('SIGINT',)`.
    """

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
