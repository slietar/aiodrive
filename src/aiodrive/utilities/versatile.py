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


@contextlib.asynccontextmanager
async def contextualize(coro: Awaitable[None], /, *, propagate: bool = True):
  origin_task = asyncio.current_task()
  assert origin_task is not None

  cancelled = False
  task = asyncio.ensure_future(coro)

  if propagate:
    def callback(task: Task[None]):
      nonlocal cancelled

      if task.exception() is not None:
        origin_task.cancel()
        cancelled = True

    task.add_done_callback(callback)

  # TODO: Errors still have to be propagated otherwise

  try:
    yield
  except asyncio.CancelledError:
    if (not cancelled) or (origin_task.cancelling() != 1):
      raise
  finally:
    await cancel_task(task)



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
