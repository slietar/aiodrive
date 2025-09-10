import asyncio
import threading
from collections.abc import Awaitable
from typing import Literal, Optional

from .shield import shield
from .thread_safe_state import ThreadsafeState

# TODO: Start thread immediately

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

    stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")

    def thread_main():
        nonlocal stage

        thread_loop.run_until_complete(thread_main_async())

        stage.set_value("join")

    async def thread_main_async():
        nonlocal stage, thread_task

        thread_task = asyncio.ensure_future(target)

        stage.set_value("running")

        await asyncio.wait([thread_task])

    thread = threading.Thread(target=thread_main)
    thread.start()

    # await stage.wait_until(lambda value: value != "preparing")

    try:
        await stage.wait_until(lambda value: value == "join")
    finally:
        assert thread_task is not None

        if stage.value == "running":
            try:
                thread_loop.call_soon_threadsafe(thread_task.cancel)
            except RuntimeError:
                # Handle a very unlikely race condition where the thread has just exited
                pass

            await stage.wait_until(lambda value: value == "join")

        thread.join()

        # This should be safe given that the thread has exited
        # It allows the exception to have a proper traceback
        return await thread_task


__all__ = [
    'run_in_thread_loop',
]


async def a():
    print("Start a")
    try:
        await asyncio.sleep(1)
    finally:
        raise Exception("Test")

    print("End a")
    return 42

async def main():
    x = await run_in_thread_loop(a())
    print(f"Result: {x}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
