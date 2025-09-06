import asyncio
import threading
from collections.abc import Awaitable
from typing import Literal, Optional

from ..misc import shield
from .thread_safe_button import ThreadSafeButton


async def run_in_thread_loop[T](target: Awaitable[T], /) -> T:
    """
    Run an awaitable in a separate thread with its own event loop.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.

    Returns
    -------
    T
        The result of the awaitable.
    """

    thread_loop = asyncio.new_event_loop()

    origin_task = asyncio.current_task()
    assert origin_task is not None

    thread_task: Optional[asyncio.Task[object]] = None

    stage: Literal["join", "preparing", "running", "terminating"] = "preparing"
    stage_change = ThreadSafeButton()

    def thread_main():
        nonlocal stage

        thread_loop.run_until_complete(thread_main_async())

        stage = "join"
        stage_change.press()

    async def thread_main_async():
        nonlocal stage, thread_task

        thread_task = asyncio.ensure_future(target)

        stage = "running"
        stage_change.press()

        await asyncio.wait([thread_task])

    thread = threading.Thread(target=thread_main)
    thread.start()

    await shield(stage_change)
    assert stage == "running"

    try:
        await stage_change
    finally:
        if stage == "running":
            try:
                thread_loop.call_soon_threadsafe(thread_task.cancel)
            except RuntimeError:
                # Handle a very unlikely race condition where the thread has just exited
                pass

            await stage_change

        assert stage == "join"
        thread.join()

        # This should be safe given that the thread has exited
        # It allows the exception to have a proper traceback
        await thread_task


__all__ = [
    'run_in_thread_loop',
]
