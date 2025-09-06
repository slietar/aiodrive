import asyncio
import contextlib
from asyncio import Future, Task
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from ..misc import cancel_task
from .scope import use_scope


class VersatileContextManager[T]:
  def __init__(self, manager: AbstractAsyncContextManager[T], /):
    self._manager = manager

  async def __aenter__(self):
    return await self._manager.__aenter__()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    return await self._manager.__aexit__(exc_type, exc_value, traceback)

  def __await__(self):
    async def inner():
      async with self._manager:
        await Future()

    return inner().__await__()


def versatile[**P, R](func: Callable[P, AbstractAsyncContextManager[R]], /):
  def inner(*args: P.args, **kwargs: P.kwargs):
    return VersatileContextManager(func(*args, **kwargs))

  return inner


class DaemonTaskFinishError(Exception):
  __slots__ = ()

@contextlib.asynccontextmanager
async def contextualize(awaitable: Awaitable[None], /, *, daemon: bool = False):
  """
  Transform an awaitable into an async context manager.

  When the context is exited, the background task created from the awaitable is
  cancelled and awaited, if still running. If the background task raises an
  exception, the current task is cancelled until exiting the context. If both
  the current and background tasks raise an exception, the exceptions are
  aggregated into an `ExceptionGroup`.

  Parameters
  ----------
  awaitable
    The awaitable to run in the background.
  daemon
    Whether the awaitable should run forever until cancelled.

  Raises
  ------
  DaemonTaskFinishError
    If `daemon` is `True` and the background task finishes successfully before
    being cancelled.
  """

  if daemon:
    async def create_target():
      await awaitable
      raise DaemonTaskFinishError

    target = create_target()
  else:
    target = awaitable

  background_task = asyncio.ensure_future(target)

  def callback(task: Task[None]):
    if not task.cancelled() and (task.exception() is not None):
      scope.cancel()

  background_task.add_done_callback(callback)

  try:
    async with use_scope() as scope:
      yield
  except asyncio.CancelledError:
    background_task.remove_done_callback(callback)

    # One of the following is possible:
    #   - The origin task is being cancelled by the user.
    #   - The background task raised an exception, which caused the origin task
    #     to be cancelled.

    await cancel_task(background_task)
    raise
  except Exception as e:
    background_task.remove_done_callback(callback)

    try:
      await cancel_task(background_task)
    except Exception as background_task_exception:
      raise ExceptionGroup("", [e, background_task_exception]) from None

    raise
  else:
    background_task.remove_done_callback(callback)
    await cancel_task(background_task)


async def main():
  async def sleep():
    raise Exception("Awake")

    try:
      await asyncio.sleep(.5)
    finally:
      print("Cleanup")
      try:
        await asyncio.sleep(1)
      finally:
        print("Cleaned up")
        raise Exception("Awake")

    print("Done")

  async with contextualize(sleep()):
    try:
      # await asyncio.sleep(0.01)
      pass
    finally:
      raise Exception("Exit context")

  print("Closing event loop")

if __name__ == "__main__":
  asyncio.run(main())
