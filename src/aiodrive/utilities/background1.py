import asyncio
import threading
from collections.abc import Awaitable
from typing import Literal, Optional

from .button1 import ThreadSafeButton


async def run_in_thread_loop[T](target: Awaitable[T], /) -> T:
    origin_loop = asyncio.get_running_loop()
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

    await stage_change
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


async def main():
    async def sleep(delay: float):
        print(f"Sleeping for {delay} seconds")

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            print(f"Sleep for {delay} seconds was cancelled")
            raise
        else:
            print(f"Finished sleeping for {delay} seconds")

    await run_in_thread_loop(sleep(2))


if __name__ == "__main__":
    asyncio.run(main())
