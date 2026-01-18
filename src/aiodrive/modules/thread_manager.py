import asyncio
from asyncio import Future, TaskGroup
from collections.abc import Awaitable

from .awaitable import wait_forever
from .event_loop import get_event_loop
from .future_state import FutureState
from .thread_loop import run_in_thread_loop_contextualized
from .thread_safe_lock import ThreadsafeLock


# def run_async(awaitable: Awaitable[T], /):
#     if get_event_loop() is not None:
#         return run_in_thread_loop_sync(awaitable)
#     else:
#         return asyncio.run(run_in_thread_loop(awaitable))


class ThreadManager:
    """
    A manager for running awaitables in a persistent separate thread with its
    own event loop.
    """

    async def _create[T](self, awaitable: Awaitable[T], future: Future[T]):
        (await FutureState.absorb_awaitable(awaitable)).transfer(future)

    async def _main(self):
        self._thread_loop = asyncio.get_running_loop()

        async with TaskGroup() as self._group:
            await wait_forever()

    def spawn_sync[T](self, awaitable: Awaitable[T], /):
        """
        Spawn an awaitable in the thread manager's event loop.

        Parameters
        ----------
        awaitable
            The awaitable to run.

        Returns
        -------
        T
            The result of the provided awaitable.
        """

        if get_event_loop() is None:
            return asyncio.run(self.spawn(awaitable))

        lock = ThreadsafeLock()
        lock.acquire_sync()

        future = Future[T]()
        future.add_done_callback(lambda f: lock.release_sync())

        self._thread_loop.call_soon_threadsafe(
            self._create,
            awaitable,
            future,
        )

        lock.acquire_sync()

        return FutureState.absorb_future(future).apply()

    async def spawn[T](self, awaitable: Awaitable[T], /):
        """
        Spawn an awaitable in the thread manager's event loop.

        Parameters
        ----------
        awaitable
            The awaitable to run.

        Returns
        -------
        T
            The result of the provided awaitable.
        """

        future = Future[T]()

        self._thread_loop.call_soon_threadsafe(
            self._create,
            awaitable,
            future,
        )

        return await future


    def __enter__(self):
        self._context_manager = run_in_thread_loop_contextualized(self._main())
        self._context_manager.__enter__()

        return self

    def __exit__(self, exc_type, exc, tb): # noqa: ANN001
        return self._context_manager.__exit__(exc_type, exc, tb)


    async def __aenter__(self):
        self._context_manager = run_in_thread_loop_contextualized(self._main())
        await self._context_manager.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc, tb): # noqa: ANN001
        return await self._context_manager.__aexit__(exc_type, exc, tb)
