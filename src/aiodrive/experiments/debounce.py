import asyncio
from collections.abc import Awaitable, Callable


def debounce[**P, R](func: Callable[P, Awaitable[R]], /, delay: float) -> tuple[Callable[P, None], Awaitable[R]]:
    """
    Debounce an asynchronous function.

    Parameters
    ----------
    func
        The asynchronous function to debounce.
    delay
        The debounce delay in seconds.

    Returns
    -------
    Callable
        A debounced version of the given function.
    """

    task = None

    async def debounced(*args: P.args, **kwargs: P.kwargs):
        nonlocal task

        if (task is not None) and not task.done():
            task.cancel()

        async def call_func():
            try:
                await asyncio.sleep(delay)
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(call_func())
        return await task

    return debounced, task
