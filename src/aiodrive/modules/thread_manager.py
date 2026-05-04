import asyncio
from asyncio import Future, Task, TaskGroup
from collections.abc import Awaitable
from typing import Any, Optional

from .awaitable import wait_forever
from .cancel import suppress
from .future_state import FutureState
from .guaranteed_task import GuaranteedTask
from .shield import shield
from .thread_loop import run_in_thread_loop_contextualized


class ThreadManager:
    """
    A class for managing the execution of awaitables in a separate thread that
    has its own event loop.

    When exiting, the thread manager waits for all tasks to finish.
    """

    def __init__(self):
        self._next_task_id = 0
        self._tasks = dict[int, Task]()


    def _cancel(self, task_id: int, message: Optional[Any]):
        task = self._tasks.get(task_id)

        if task is not None:
            task.cancel(message)

    def _create[T](self, task_id: int, awaitable: Awaitable[T], future: Future[T]):
        async def create_task():
            try:
                (await FutureState.absorb_awaitable(inner_task)).transfer_threadsafe(future)
            finally:
                del self._tasks[task_id]

        async def coro():
            return await awaitable

        inner_task = GuaranteedTask(coro())
        self._tasks[task_id] = inner_task
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

        task_id = self._next_task_id
        self._next_task_id += 1

        future = Future[T]()

        self._thread_loop.call_soon_threadsafe(
            self._create,
            task_id,
            awaitable,
            future,
        )

        cancelled = False

        while True:
            try:
                result = await shield(future)
            except asyncio.CancelledError as e:
                if future.done():
                    raise

                with suppress(RuntimeError):
                    self._thread_loop.call_soon_threadsafe(self._cancel, task_id, e.args[0] if e.args else None)
            else:
                break

        if cancelled:
            raise asyncio.CancelledError

        return result

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
