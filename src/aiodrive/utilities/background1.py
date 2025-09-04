import asyncio
import threading
from asyncio import Future
from collections.abc import Awaitable
from typing import Optional

from .button1 import ThreadSafeButton
from .versatile import contextualize


async def run_in_thread_loop[T](target: Awaitable[T], /) -> T:
    origin_loop = asyncio.get_running_loop()
    thread_loop = asyncio.new_event_loop()

    origin_task = asyncio.current_task()
    assert origin_task is not None

    thread_exception: Optional[Exception] = None
    thread_result: Optional[T] = None

    thread_task: Optional[asyncio.Task] = None
    button = ThreadSafeButton()

    def thread_main():
        thread_loop.run_until_complete(thread_main_async())
        button.press()

    async def thread_main_async():
        nonlocal thread_exception, thread_result, thread_task

        thread_task = asyncio.current_task()
        button.press()

        try:
            thread_result = await target
        except asyncio.CancelledError:
            pass
        except Exception as e:
            origin_loop.call_soon_threadsafe(origin_task.cancel)
            thread_exception = e

    thread = threading.Thread(target=thread_main)
    thread.start()

    await button

    try:
        await Future()
    finally:
        assert thread_task is not None

        if thread_loop.is_running():
            thread_loop.call_soon_threadsafe(thread_task.cancel)
            # Problem: the loop could have been stopped running
            # Problem: the button could have been pressed already
            await button

        thread.join()

        if thread_exception is not None:
            raise thread_exception from None

        return thread_result


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

    try:
        async with contextualize(run_in_thread_loop(sleep(1))):
            await asyncio.sleep(1.5)
            # Or
            # await asyncio.sleep(.5)
            print("Closing")
    except Exception as e:
        raise Exception("An error occurred") from e

    print("Closed")


if __name__ == "__main__":
    asyncio.run(main())
