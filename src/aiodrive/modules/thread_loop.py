import asyncio
import contextvars
from asyncio import Future
from collections.abc import Awaitable
from threading import Thread
from typing import Literal, Optional

from ..internal.future import ensure_future
from .bivalent_context_manager import bivalent_context_manager
from .contextualize import contextualize
from .future_state import FutureState
from .shield import shield_wait_forever
from .thread_safe_state import ThreadsafeState
from .thread_sync import run_in_thread_loop_contextualized_sync


async def launch_in_thread_loop[T](target: Awaitable[T], /, use_executor: bool = True) -> Awaitable[T]:
    """
    Launch an awaitable in a separate thread with its own event loop.

    This function returns after the first iteration of the event loop in the
    thread has completed.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread.
    use_executor
        Whether to use one of the event loop's executors instead of creating a
        new thread.

    Returns
    -------
    Awaitable[T]
        An awaitable which resolves to the result of the provided awaitable. The
        returned value must be awaited.
    """

    result: Optional[FutureState[T]] = None
    stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
    task: Optional[Future[T]] = None

    def thread_main():
        nonlocal result, stage

        result = FutureState.absorb_lambda(asyncio.run, thread_main_async())
        stage.set_value("join")

    async def thread_main_async():
        nonlocal stage, task

        loop = asyncio.get_running_loop()

        task = ensure_future(target)
        loop.call_soon(stage.set_value, "running")

        return await task


    context = contextvars.copy_context()

    if use_executor:
        loop = asyncio.get_running_loop()

        thread = None
        thread_future = loop.run_in_executor(None, context.run, thread_main)
    else:
        thread = Thread(target=context.run, args=(thread_main,))
        thread.start()
        thread_future = None


    # Wait for the task to start

    cancelled = False

    while True:
        try:
            # Wait no matter what for the task to at least start
            await stage.wait_until(lambda value: value != "preparing")
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
            except asyncio.CancelledError:
                cancelled = True

                # Attempt to cancel the task
                try:
                    task.get_loop().call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass
            else:
                break

        if use_executor:
            assert thread_future is not None
            await shield_wait_forever(thread_future)
        else:
            assert thread is not None
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

    This function returns once the thread has terminated.

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


# Not public
async def run_in_thread_loop_contextualized_async(target: Awaitable[None], /):
    """
    Run an awaitable in a separate thread with its own event loop, using a
    context manager.

    The context manager's entry completes once the first iteration of the event
    loop of the thread has completed.

    Parameters
    ----------
    target
        The awaitable to run in a separate thread. Its return value is discarded.

    Returns
    -------
    AbstractAsyncContextManager[None]
        An async context manager which runs the provided awaitable in a separate
        thread.
    """

    async with contextualize(
        await launch_in_thread_loop(target, use_executor=False),
    ):
        yield


run_in_thread_loop_contextualized = bivalent_context_manager(
    run_in_thread_loop_contextualized_sync,
    run_in_thread_loop_contextualized_async,
)


__all__ = [
    'launch_in_thread_loop',
    'run_in_thread_loop',
    'run_in_thread_loop_contextualized',
]
