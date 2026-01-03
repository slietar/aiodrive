import asyncio
import contextlib
from asyncio import Future, Task
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from signal import Signals

from ..modules.contextualize import contextualize
from ..modules.future_state import FutureState
from ..modules.shield import shield
from ..modules.thread_sync import to_thread


async def recv_connection(conn: Connection, /):
    """
    Receive a message from a multiprocessing `Connection`.

    Parameters
    ----------
    conn
        The `Connection` to receive the message from.

    Returns
    -------
    Any
        The received message.
    """

    job = asyncio.ensure_future(to_thread(conn.recv))

    try:
        return await shield(job)
    except asyncio.CancelledError:
        conn.close()

        with contextlib.suppress(IOError):
            await job

        raise


@dataclass(slots=True)
class CreateTaskMessage:
    task_id: int
    target: Callable[..., Awaitable]
    args: tuple
    kwargs: dict

@dataclass(slots=True)
class CancelTaskMessage:
    task_id: int

@dataclass(slots=True)
class FinishTaskMessage:
    state: FutureState
    task_id: int


# This must be publicly available
def process_main(conn: Connection):
    asyncio.run(process_main_async(conn))

async def process_main_async(conn: Connection):
    # Prevent SIGINT from propagating to the child process
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(Signals.SIGINT, lambda: None)

    tasks = dict[int, Task]()

    def task_done_callback(task_id: int):
        task = tasks.pop(task_id)
        state = FutureState.absorb_future(task)

        conn.send(FinishTaskMessage(state, task_id))

    while True:
        try:
            message: CreateTaskMessage | CancelTaskMessage = await to_thread(conn.recv)
        except EOFError:
            assert not tasks
            break

        match message:
            case CreateTaskMessage():
                task = asyncio.ensure_future(message.target(*message.args, **message.kwargs))
                task.add_done_callback(lambda task, task_id = message.task_id: task_done_callback(task_id))
                tasks[message.task_id] = task
            case CancelTaskMessage():
                task = tasks.get(message.task_id)

                # The task may be none if it finished before the cancel message
                # was processed
                if task is not None:
                    task.cancel()
            case _:
                raise ValueError


class AsyncProcess:
    """
    A class for managing asynchronous tasks in a separate process.
    """

    async def __aenter__(self):
        self._tasks = dict[int, Future]()
        self._next_task_id = 0
        self._server_conn, client_conn = Pipe()

        self._process = Process(target=process_main, args=(client_conn,))
        self._process.start()

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        async def close_callback1():
            await to_thread(self._process.join)

            if self._process.exitcode != 0:
                raise RuntimeError(f"Process exited with code {self._process.exitcode}")

        self._stack.push_async_callback(close_callback1)
        await self._stack.enter_async_context(contextualize(self._loop()))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
        return await self._stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _loop(self):
        while True:
            message: FinishTaskMessage = await recv_connection(self._server_conn)

            future = self._tasks.pop(message.task_id)
            message.state.transfer(future)

    async def spawn[**P, R](self, func: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs):
        """
        Spawn an asynchronous function in the separate process.

        Cancellation is propagated to the function.

        Parameters
        ----------
        func
            The asynchronous function to run.
        *args
            Positional arguments to pass to the function.
        **kwargs
            Keyword arguments to pass to the function.

        Returns
        -------
        R
            The result of the function.
        """

        task_id = self._next_task_id
        self._next_task_id += 1

        self._server_conn.send(
            CreateTaskMessage(
                task_id=task_id,
                target=func,
                args=args,
                kwargs=kwargs,
            ),
        )

        future = Future[R]()
        self._tasks[task_id] = future

        while True:
            try:
                return await asyncio.shield(future)
            except asyncio.CancelledError:
                if future.done():
                    raise

                self._server_conn.send(CancelTaskMessage(task_id=task_id))


async def run_in_process[**P, R](func: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs) -> R:
    """
    Run an asynchronous function in a separate process.

    Cancellation is propagated to the function.

    Parameters
    ----------
    func
        The asynchronous function to run.
    *args
        Positional arguments to pass to the function.
    **kwargs
        Keyword arguments to pass to the function.

    Returns
    -------
    R
        The result of the function.
    """

    async with AsyncProcess() as process:
        return await process.spawn(func, *args, **kwargs)


__all__ = [
    "AsyncProcess",
    "recv_connection",
    "run_in_process",
]
