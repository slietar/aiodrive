import asyncio
from asyncio import Future, Task
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from signal import Signals
from types import CoroutineType
from typing import Any

import aiodrive

from .to_thread import to_thread_patient


@dataclass(slots=True)
class CreateTaskMessage:
    task_id: int
    target: Callable[..., CoroutineType]
    args: tuple
    kwargs: dict

@dataclass(slots=True)
class CancelTaskMessage:
    task_id: int


# TODO: Race condition between CancelTaskMessage and FinishTaskMessage
@dataclass(slots=True)
class FinishTaskMessage:
    state: aiodrive.FutureState
    task_id: int


# This must be publicly available
def process_main(conn: Connection):
    asyncio.run(process_main_async(conn))

async def process_main_async(conn: Connection):
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(Signals.SIGINT, lambda: None)

    tasks = dict[int, Task]()

    async def handle_messages():
        while True:
            try:
                message: CreateTaskMessage | CancelTaskMessage = await to_thread_patient(conn.recv)
            except EOFError:
                assert not tasks
                break

            match message:
                case CreateTaskMessage():
                    task = asyncio.create_task(message.target(*message.args, **message.kwargs))
                    task.add_done_callback(lambda task, task_id = message.task_id: task_done_callback(task_id))
                    tasks[message.task_id] = task
                case CancelTaskMessage():
                    tasks[message.task_id].cancel()
                case _:
                    raise ValueError

    def task_done_callback(task_id: int):
        task = tasks.pop(task_id)
        state = aiodrive.FutureState.absorb_future(task)

        conn.send(FinishTaskMessage(state, task_id))

    await handle_messages()


async def recv_conn(conn: Connection):
    job = asyncio.create_task(to_thread_patient(conn.recv))

    try:
        return await asyncio.shield(job)
    except asyncio.CancelledError:
        conn.close()

        with aiodrive.suppress(IOError):
            await job

        raise


class AsyncProcess:
    async def __aenter__(self):
        self._tasks = dict[int, Future]()
        self._next_task_id = 0
        self._server_conn, client_conn = Pipe()

        self._process = Process(target=process_main, args=(client_conn,))
        self._process.start()

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        self._scope = aiodrive.use_scope()
        self._stack.enter_context(self._scope)

        async def close_callback1():
            await to_thread_patient(self._process.join)

        self._stack.push_async_callback(close_callback1)

        await self._stack.enter_async_context(aiodrive.contextualize(self._loop()))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
        return await self._stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _loop(self):
        while True:
            message: FinishTaskMessage = await recv_conn(self._server_conn)

            future = self._tasks.pop(message.task_id)
            message.state.transfer(future)

    async def spawn[**P, R](self, func: Callable[P, CoroutineType[None, Any, R]], *args: P.args, **kwargs: P.kwargs):
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


# class AsyncProcess[**P, T]:
#     def __init__(self, factory: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> None:
#         self._factory = factory
#         self._args = args
#         self._kwargs = kwargs

#     async def __aenter__(self) -> T:
#         server_conn, client_conn = Pipe()
#         server_conn.recv()

#         self._process = Process(
#             target=process_main,
#             args=(client_conn, *self._args),
#             kwargs=self._kwargs,
#         )

#         self._process.start()

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         self._process.join()

# class Math:
#     def square(self, x: int):
#         return x * x

async def a(x: float):
    global state

    if "state" not in globals():
        state = 0

    print(f"Sleeping {x}")
    await asyncio.sleep(x)

    state += x
    print(f"Slept {x} {state}")

    return x

async def main():
    try:
        with aiodrive.handle_signal(Signals.SIGINT):
            async with AsyncProcess() as proc:
                print(
                    await aiodrive.gather(
                        proc.spawn(a, .5),
                        proc.spawn(a, 1),
                        proc.spawn(a, 2),
                    ),
                )
    except* aiodrive.SignalHandledException:
        print("Operation cancelled by user.")

if __name__ == "__main__":
    # with Pool(processes=4) as pool:
    #     results = pool.map(square, range(10))
    #     print(results)

    asyncio.run(main())
