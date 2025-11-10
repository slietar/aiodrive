import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable
from threading import Thread
from typing import Literal, Optional

from .contextualize import contextualize
from .future_state import FutureState
from .run import run
from .shield import shield
from .thread_safe_state import ThreadsafeState


# TODO: Fix event loop leakage
# TODO: Test sys.exit()

async def launch_in_thread_loop[T](target: Awaitable[T], /) -> Awaitable[T]:
    """
    Launch an awaitable in a separate thread with its own event loop.

    This function returns after the first iteration of the event loop in the
    thread has completed.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.

    Returns
    -------
    Awaitable[T]
        An awaitable which resolves to the result of the provided awaitable. The
        returned value must be awaited.
    """

    loop = asyncio.new_event_loop()
    result: Optional[FutureState[T]] = None
    stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
    task: Optional[asyncio.Task[T]] = None

    def thread_main():
        nonlocal result, stage

        result = FutureState.absorb_lambda(run, thread_main_async(), loop=loop)
        stage.set_value("join")

    async def thread_main_async():
        nonlocal stage, task

        task = asyncio.ensure_future(target)
        loop.call_soon(stage.set_value, "running")

        return await task

    thread = Thread(target=thread_main)
    thread.start()

    async def wait():
        try:
            await stage.wait_until(lambda value: value == "join")
        finally:
            assert task is not None

            if stage.value == "running":
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    # Handle a very unlikely race condition where the thread has
                    # just exited and the thread loop is closed
                    pass

                await stage.wait_until(lambda value: value == "join")

            thread.join()

            # This should be safe given that the thread has exited
            # It allows the exception to have a proper traceback
            # result = await thread_task

        # assert result is not None

    try:
        await shield(stage.wait_until(lambda value: value != "preparing"))
    except asyncio.CancelledError:
        assert task is not None
        loop.call_soon_threadsafe(task.cancel)

        raise

    async def finish():
        await wait()

        assert result is not None
        return result.apply()

    return finish()


async def run_in_thread_loop[T](target: Awaitable[T], /) -> T:
    """
    Run an awaitable in a separate thread with its own event loop.

    This function returns once the other thread has terminated.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.

    Returns
    -------
    T
        The result of the provided awaitable.
    """

    return await (await launch_in_thread_loop(target))


@contextlib.asynccontextmanager
async def run_in_thread_loop_contextualized(target: Awaitable[None], /) -> AsyncIterator[None]:
    """
    Run an awaitable in a separate thread with its own event loop, using a
    context manager.

    The context manager's entry completes once the first iteration of the event
    loop of the thread has completed.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.

    Returns
    -------
    AsyncContextManager[None]
        An async context manager which runs the provided awaitable in a separate
        thread.
    """

    async with contextualize(
        await launch_in_thread_loop(target),
    ):
        yield


__all__ = [
    'launch_in_thread_loop',
    'run_in_thread_loop',
    'run_in_thread_loop_contextualized',
]



if __name__ == "__main__":
    import sys
    import time
    import warnings

    warnings.resetwarnings()

    async def a():
        # time.sleep(1)
        # sys.exit(1)
        # raise SystemExit(2)
        # raise BaseException("Test exception")
        await asyncio.sleep(1)

    async def main():
        await run_in_thread_loop(a())
        # # task = asyncio.create_task(a())
        # print("Created task")

        # try:
        #     await asyncio.sleep(1)
        # finally:
        #     await task


    # import asyncio
    # asyncio.run(main())
    asyncio.run(main())


    # try:
    #     raise Exception("Test exception")
    # except:
    #     pass
    # finally:
    #     print(">>", repr(sys.exception()))
