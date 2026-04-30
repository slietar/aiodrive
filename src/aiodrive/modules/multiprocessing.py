import asyncio
import pickle
import socket
from asyncio import Future, StreamReader, StreamWriter
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from multiprocessing import Process
from signal import Signals
from typing import Any

from .contextualize import contextualize
from .future_state import FutureState
from .process import wait_for_process
from .shield import shield
from .task_group import volatile_task_group


@dataclass(slots=True)
class Connection:
    _reader: StreamReader
    _writer: StreamWriter

    async def recv(self):
        size_bytes = await self._reader.read(4)

        if not size_bytes:
            raise EOFError

        size = int.from_bytes(size_bytes)
        return pickle.loads(await self._reader.read(size))

    async def send(self, data: bytes):
        size = len(data)
        size_bytes = size.to_bytes(4)

        self._writer.write(size_bytes)
        self._writer.write(data)

        await self._writer.drain()

    async def send_object(self, obj: Any):
        await self.send(pickle.dumps(obj))


async def create_pipe():
    parent_socket, client_socket = socket.socketpair()
    reader, writer = await asyncio.open_connection(sock=parent_socket)

    return (
        Connection(reader, writer),
        client_socket,
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
def process_main(client_socket: socket.socket):
    asyncio.run(process_main_async(client_socket))

async def process_main_async(client_socket: socket.socket):
    # conn = await ser_conn.to_connection()
    reader, writer = await asyncio.open_connection(sock=client_socket)
    conn = Connection(reader, writer)

    # Prevent SIGINT from propagating to the child process
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(Signals.SIGINT, lambda: None)

    tasks = dict[int, Future]()

    async def wait_task(message: CreateTaskMessage):
        state = await FutureState.absorb_awaitable(message.target(*message.args, **message.kwargs))

        try:
            data = pickle.dumps(FinishTaskMessage(state, message.task_id))
        except (TypeError, pickle.PicklingError) as e:
            state = FutureState.new_failed(e)
            data = pickle.dumps(FinishTaskMessage(state, message.task_id))

        del tasks[message.task_id]
        await conn.send(data)

    async with volatile_task_group() as group:
        while True:
            message = await conn.recv()

            match message:
                case CreateTaskMessage():
                    task = group.create_task(wait_task(message))
                    tasks[message.task_id] = task
                case CancelTaskMessage():
                    task = tasks.get(message.task_id)

                    # The task may be None if it finished before the cancel
                    # message was processed
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
        self._server_conn, client_socket = await create_pipe()

        self._process = Process(target=process_main, args=(client_socket,))
        self._process.start()

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        async def close_callback():
            with suppress(IOError):
                await self._server_conn.send_object(ShutdownMessage())

            assert self._process.pid is not None
            await wait_for_process(self._process.pid)

            self._process.join()

            assert self._process.exitcode is not None

            if self._process.exitcode != 0:
                raise RuntimeError(f"Process exited with code {self._process.exitcode}")

        # First kill the process, which will cause an EOFError to be raised in
        # _loop() and an exception to be set in all pending tasks
        self._stack.push_async_callback(close_callback)
        await self._stack.enter_async_context(contextualize(self._loop()))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
        return await self._stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _loop(self):
        while True:
            try:
                message: FinishTaskMessage = await self._server_conn.recv()
            except EOFError:
                for future in self._tasks.values():
                    future.set_exception(ConnectionError("Connection closed"))

                self._tasks.clear()
                break
            else:
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

        await self._server_conn.send_object(
            CreateTaskMessage(
                task_id=task_id,
                target=func,
                args=args,
                kwargs=kwargs,
            ),
        )

        cancelled = False
        future = Future[R]()
        self._tasks[task_id] = future

        while True:
            try:
                result = await shield(future)
            except asyncio.CancelledError:
                # Occurs if the task itself raises CancelledError
                if future.done():
                    raise

                cancelled = True

                await self._server_conn.send_object(CancelTaskMessage(task_id=task_id))
            else:
                break

        # The task finished successfully before it could be cancelled, so we
        # return a synthetic CancelledError
        if cancelled:
            raise asyncio.CancelledError

        return result



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
