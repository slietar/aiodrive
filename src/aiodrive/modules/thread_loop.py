import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator, Awaitable
from typing import Literal, Optional

from .contextualize import contextualize
from .thread_safe_state import ThreadsafeState


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

    thread_loop = asyncio.new_event_loop()
    thread_task: Optional[asyncio.Task[T]] = None

    stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")

    def thread_main():
        nonlocal stage

        thread_loop.run_until_complete(thread_main_async())
        stage.set_value("join")

    async def thread_main_async():
        nonlocal stage, thread_task

        thread_task = asyncio.ensure_future(target)
        thread_loop.call_soon(stage.set_value, "running")

        await asyncio.wait([thread_task])

    thread = threading.Thread(target=thread_main)
    thread.start()

    async def wait():
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

    try:
        await stage.wait_until(lambda value: value != "preparing")
    except:
        await wait()
        raise

    return wait()


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
async def run_in_thread_loop_contextualized(target: Awaitable[None], /, *, daemon: bool = False) -> AsyncIterator[None]:
    """
    Run an awaitable in a separate thread with its own event loop, using a
    context manager.

    The context manager's entry completes once the first iteration of the event
    loop of the thread has completed.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.
    daemon
        See `contextualize`.

    Returns
    -------
    AsyncContextManager[None]
        An async context manager which runs the provided awaitable in a separate
        thread.
    """

    async with contextualize(
        await launch_in_thread_loop(target),
        daemon=daemon,
    ):
        yield


__all__ = [
    'launch_in_thread_loop',
    'run_in_thread_loop',
    'run_in_thread_loop_contextualized',
]
