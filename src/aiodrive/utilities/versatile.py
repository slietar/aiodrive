import asyncio
import contextlib
from asyncio import Future, Task
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from ..misc import cancel_task


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

  TODO: Details

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

  origin_task = asyncio.current_task()
  assert origin_task is not None

  if daemon:
    async def create_target():
      await awaitable
      raise DaemonTaskFinishError

    target = create_target()
  else:
    target = awaitable

  background_task = asyncio.ensure_future(target)

  def callback(task: Task[None]):
    # If the task was not cancelled, it means the origin task is still running.
    if not task.cancelled() and (task.exception() is not None):
      origin_task.cancel()

  background_task.add_done_callback(callback)

  try:
    yield
  except asyncio.CancelledError:
    # One of the following is possible:
    #   - The origin task is being cancelled by the user.
    #   - The background task raised an exception, which caused the origin task
    #     to be cancelled.

    await cancel_task(background_task)
    raise
  except Exception as e:
    try:
      await cancel_task(background_task)
    except Exception as background_task_exception:
      raise ExceptionGroup("", [e, background_task_exception]) from None

    raise
  else:
    await cancel_task(background_task)



async def main():
  @versatile
  @contextlib.asynccontextmanager
  async def sleep():
    print("Start")
    await asyncio.sleep(.5)

    try:
      yield
    finally:
      print("Cleanup")
      await asyncio.sleep(.5)

    print("Done")

  async with sleep():
    print("In context manager")
    # await asyncio.sleep(1)
    raise RuntimeError("Test")

if __name__ == "__main__":
  asyncio.run(main())
