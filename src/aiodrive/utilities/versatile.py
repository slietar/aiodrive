import asyncio
import contextlib
from asyncio import Future
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from ..misc import cancel_task


# class AsyncContextManagerOrAwaitable[T]:
#   def __init__(self, func: Callable[[], AsyncGenerator[T]], /):
#     self._agen: Optional[AsyncGenerator[T]] = None
#     self._func = func

#   async def __aenter__(self) -> T:
#     if self._agen is not None:
#       raise RuntimeError("Context manager already entered")

#     self._agen = self._func()

#     try:
#       return await anext(self._agen)
#     except StopAsyncIteration:
#       raise RuntimeError("Async generator didn't yield") from None

#   async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # noqa: ANN001
#     if self._agen is None:
#       raise RuntimeError("Context manager not entered")

#     try:
#       await anext(self._agen)
#     except StopAsyncIteration:
#       pass
#     else:
#       raise RuntimeError("Async generator didn't stop")

#   async def __await__(self):
#     async with self:
#       await Future()


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
async def contextualize(coro: Awaitable[None], /):
  task = asyncio.ensure_future(coro)

  try:
    yield
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
