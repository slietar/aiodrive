import asyncio
import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from threading import Thread
from typing import Literal, Optional

from .cancel import suppress
from .future_state import FutureState
from .thread_safe_state import ThreadsafeState


class AbstractDoubleContextManager[T](AbstractContextManager[T], AbstractAsyncContextManager[T]):
  pass

def double_context_manager[**P, T](
  sync_handler: Callable[P, Generator[T]],
  async_handler: Callable[P, AsyncGenerator[T]],
  /,
) -> Callable[P, AbstractDoubleContextManager[T]]:
  async_manager_factory = contextlib.asynccontextmanager(async_handler)
  sync_manager_factory = contextlib.contextmanager(sync_handler)

  class DoubleContextManager:
    def __init__(self, *args: P.args, **kwargs: P.kwargs):
      self._args = args
      self._kwargs = kwargs

    async def __aenter__(self) -> T:
      self._async_manager = async_manager_factory(*self._args, **self._kwargs)
      return await self._async_manager.__aenter__()

    async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
      return await self._async_manager.__aexit__(exc_type, exc_value, traceback)

    def __enter__(self) -> T:
      self._sync_manager = sync_manager_factory(*self._args, **self._kwargs)
      return self._sync_manager.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
      return self._sync_manager.__exit__(exc_type, exc_value, traceback)

  return DoubleContextManager # type: ignore


# TODO: Integrate into run_in_thread_loop_contextualized

def run_in_thread_loop_contextualized_sync[T](target: Awaitable[T], /):
  result: Optional[FutureState[T]] = None
  stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
  task: Optional[asyncio.Task[T]] = None

  def thread_main():
    nonlocal result, stage

    result = FutureState.absorb_lambda(asyncio.run, thread_main_async())
    stage.set_value("join")

  async def thread_main_async():
    nonlocal task

    loop = asyncio.get_running_loop()

    task = asyncio.ensure_future(target)
    loop.call_soon(stage.set_value, "running")

    return await task

  thread = Thread(target=thread_main)
  thread.start()

  try:
    stage.wait_until_sync(lambda value: value == "running")
    yield
  finally:
    assert task is not None

    try:
      task.get_loop().call_soon_threadsafe(task.cancel)
    except RuntimeError:
      pass

    stage.wait_until_sync(lambda value: value == "join")
    thread.join()

  with suppress(asyncio.CancelledError):
    result.apply()
