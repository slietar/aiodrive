import asyncio
import threading
from asyncio import Future
from collections.abc import Awaitable
from typing import Optional

from .versatile import contextualize


# Is it possible to initialize coroutine in new thread and await it in original thread?


async def run_in_thread_loop(target: Awaitable[None], /):
    origin_loop = asyncio.get_running_loop()
    thread_loop = asyncio.new_event_loop()

    origin_task = asyncio.current_task()
    assert origin_task is not None

    thread_exception: Optional[Exception] = None
    thread_task: Optional[asyncio.Task] = None
    ready_event = threading.Event()

    def thread_main():
        thread_loop.run_until_complete(thread_main_async())

    async def thread_main_async():
        nonlocal thread_exception, thread_task

        thread_task = asyncio.current_task()
        ready_event.set()

        try:
            await target
        except asyncio.CancelledError:
            pass
        except Exception as e:
            origin_loop.call_soon_threadsafe(origin_task.cancel)
            thread_exception = e

    thread = threading.Thread(target=thread_main)
    thread.start()

    ready_event.wait()

    try:
        await Future()
    finally:
        assert thread_task is not None

        if thread_loop.is_running():
            thread_loop.call_soon_threadsafe(thread_task.cancel)

        thread.join()

        if thread_exception is not None:
            raise thread_exception from None


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
