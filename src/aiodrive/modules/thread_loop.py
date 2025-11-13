import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable
from threading import Thread
from typing import Literal, Optional

from .contextualize import contextualize
from .future_state import FutureState
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

    result: Optional[FutureState[T]] = None
    stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
    task: Optional[asyncio.Task[T]] = None

    def thread_main():
        nonlocal result, stage

        result = FutureState.absorb_lambda(asyncio.run, thread_main_async())
        stage.set_value("join")

    async def thread_main_async():
        nonlocal stage, task

        loop = asyncio.get_running_loop()

        task = asyncio.ensure_future(target)
        loop.call_soon(stage.set_value, "running")

        return await task

    thread = Thread(target=thread_main)
    thread.start()


    # Wait for the task to start

    cancelled = False

    while True:
        try:
            # Wait no matter what for the task to at least start
            await asyncio.shield(stage.wait_until(lambda value: value != "preparing"))
        except asyncio.CancelledError:
            cancelled = True
        else:
            break

    if cancelled:
        assert task is not None

        try:
            task.get_loop().call_soon_threadsafe(task.cancel)
        except RuntimeError:
            pass


    # Wait for the task to finish

    async def finish():
        nonlocal cancelled

        assert task is not None

        while True:
            try:
                await stage.wait_until(lambda value: value == "join")
            except asyncio.CancelledError as e:
                cancelled = e

                # Attempt to cancel the task
                try:
                    task.get_loop().call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass
            else:
                break

        thread.join()

        assert result is not None
        value = result.apply()

        # In case the task suppressed the CancelledError
        if cancelled:
            raise asyncio.CancelledError

        return value

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
    AbstractAsyncContextManager[None]
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
