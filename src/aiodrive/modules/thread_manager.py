import asyncio
from asyncio import Future, TaskGroup
from collections.abc import Awaitable

from .awaitable import wait_forever
from .future_state import FutureState
from .thread_loop import run_in_thread_loop_contextualized


class ThreadManager:
    """
    A class for managing the execution of awaitables in a separate thread that
    has its own event loop.
    """

    def _create[T](self, awaitable: Awaitable[T], future: Future[T]):
        async def create_task():
            (await FutureState.absorb_awaitable(awaitable)).transfer_threadsafe(future)

        self._group.create_task(create_task())

    async def _main(self):
        self._thread_loop = asyncio.get_running_loop()

        async with TaskGroup() as self._group:
            await wait_forever()

    def spawn_sync[T](self, awaitable: Awaitable[T], /):
        """
        Spawn an awaitable in the thread manager's event loop.

        This method may only be called if there is no running event loop.

        Parameters
        ----------
        awaitable
            The awaitable to run.

        Returns
        -------
        T
            The result of the provided awaitable.
        """

        return asyncio.run(self.spawn(awaitable))

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
