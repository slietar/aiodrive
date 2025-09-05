import asyncio
import threading
from asyncio import Future
from collections.abc import Awaitable
from typing import Literal, Optional

from .future_state import FutureState

from .button1 import ThreadSafeButton
from .versatile import contextualize


async def run_in_thread_loop[T](target: Awaitable[T], /) -> T:
    origin_loop = asyncio.get_running_loop()
    thread_loop = asyncio.new_event_loop()

    origin_task = asyncio.current_task()
    assert origin_task is not None

    thread_state: Optional[FutureState[T]] = None
    thread_task: Optional[asyncio.Task[object]] = None

    stage: Literal["join", "preparing", "running", "terminating"] = "preparing"
    stage_change = ThreadSafeButton()

    def thread_main():
        thread_loop.run_until_complete(thread_main_async())

    async def thread_main_async():
        nonlocal stage, thread_state, thread_task

        thread_task = asyncio.current_task()

        stage = "running"
        stage_change.press()

        thread_state = await FutureState.absorb_awaitable(target)

        stage = "join"
        stage_change.press()

    thread = threading.Thread(target=thread_main)
    thread.start()

    await stage_change
    assert stage == "running"

    try:
        await stage_change
    finally:
        if stage_change == "running":
            try:
                thread_loop.call_soon_threadsafe(thread_task.cancel)
            except RuntimeError:
                # Handle a very unlikely race condition where the thread has just exited
                pass

            await stage_change

        assert stage == "join"
        thread.join()

        assert thread_state is not None
        return thread_state.apply()

        # TODO: Maybe wrap error in exception group for readability


async def main():
    async def sleep(delay: float):
        print(f"Sleeping for {delay} seconds")

        try:
            await asyncio.sleep(delay)
            raise ValueError("An error occurred during sleep")
        except asyncio.CancelledError:
            print(f"Sleep for {delay} seconds was cancelled")
            raise
        else:
            print(f"Finished sleeping for {delay} seconds")

    await run_in_thread_loop(sleep(2))

    # try:
    #     async with contextualize(run_in_thread_loop(sleep(1))):
    #         await asyncio.sleep(1.5)
    #         # Or
    #         # await asyncio.sleep(.5)
    #         print("Closing")
    # except Exception as e:
    #     raise Exception("An error occurred") from e

    # print("Closed")


if __name__ == "__main__":
    asyncio.run(main())
