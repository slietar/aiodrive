import asyncio
import os
import pickle
import socket
import struct
from asyncio import Future, StreamReader, StreamWriter
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from multiprocessing import Process
from signal import Signals
from typing import Any

from .contextualize import contextualize
from .future_state import FutureState
from .task_group import volatile_task_group
from .thread_sync import to_thread


@dataclass(slots=True)
class Connection:
    _reader: StreamReader
    _writer: StreamWriter

    async def read(self):
        size_bytes = await self._reader.read(4)
        size, = struct.unpack("!i", size_bytes)

        x = pickle.loads(await self._reader.read(size))
        print("Received", os.getpid(), x)
        return x

    async def send(self, obj: Any):
        print("Sending", os.getpid(), obj)

        data = pickle.dumps(obj)
        size = len(data)
        size_bytes = struct.pack("!i", size)

        self._writer.write(size_bytes)
        self._writer.write(data)

        await self._writer.drain()


async def create_pipe():
    parent_sock, child_sock = socket.socketpair()
    reader, writer = await asyncio.open_connection(sock=parent_sock)

    return (
        Connection(reader, writer),
        child_sock,
    )


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

@dataclass(slots=True)
class ShutdownMessage:
    pass


# This must be publicly available
def process_main(conn):
    asyncio.run(process_main_async(conn))

async def process_main_async(ser_conn: socket.socket):
    # conn = await ser_conn.to_connection()
    reader, writer = await asyncio.open_connection(sock=ser_conn)
    conn = Connection(reader, writer)

    # Prevent SIGINT from propagating to the child process
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(Signals.SIGINT, lambda: None)

    tasks = dict[int, Future]()

    async with volatile_task_group() as group:
        while True:
            try:
                message: CreateTaskMessage | CancelTaskMessage = await conn.read()
            except EOFError:
                assert not tasks
                break

            match message:
                case CreateTaskMessage():
                    async def wait_task(message: CreateTaskMessage):
                        state = await FutureState.absorb_awaitable(
                            message.target(*message.args, **message.kwargs),
                        )

                        await conn.send(FinishTaskMessage(state, message.task_id))

                    task = group.create_task(wait_task(message))
                    tasks[message.task_id] = task
                case CancelTaskMessage():
                    task = tasks.get(message.task_id)

                    # The task may be none if it finished before the cancel message
                    # was processed
                    if task is not None:
                        task.cancel()
                case ShutdownMessage():
                    break
                case _:
                    raise ValueError


class MultiprocessingProcess:
    """
    A class for managing asynchronous tasks in a separate process.
    """

    async def __aenter__(self):
        self._tasks = dict[int, Future]()
        self._next_task_id = 0
        self._server_conn, client_conn = await create_pipe()

        self._process = Process(target=process_main, args=(client_conn,))
        self._process.start()

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        async def close_callback():
            await self._server_conn.send(ShutdownMessage())

            await to_thread(self._process.join)

            if self._process.exitcode != 0:
                raise RuntimeError(f"Process exited with code {self._process.exitcode}")

        self._stack.push_async_callback(close_callback)
        await self._stack.enter_async_context(contextualize(self._loop()))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
        return await self._stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _loop(self):
        while True:
            message: FinishTaskMessage = await self._server_conn.read()

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

        await self._server_conn.send(
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

                await self._server_conn.send(CancelTaskMessage(task_id=task_id))


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

    async with MultiprocessingProcess() as process:
        return await process.spawn(func, *args, **kwargs)


__all__ = [
    "MultiprocessingProcess",
    "run_in_process",
]
