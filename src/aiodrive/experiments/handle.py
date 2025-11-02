import asyncio
from collections.abc import AsyncIterator, Awaitable

from ..modules.cancel import cancel_task
from ..modules.contextualize import contextualize


class Handle[T]:
  def __init__(self, awaitable: Awaitable[T], /):
    self._task = asyncio.ensure_future(awaitable)

  def __await__(self):
    return self._task.__await__()

  async def __aenter__(self):
    async def func():
      await self._task

    self._contextualized = contextualize(func(), daemon=True)
    await self._contextualized.__aenter__()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)

  async def aclose(self):
    await cancel_task(self._task)


class PendingHandle[T, S]:
  def __init__(self, awaitable: Awaitable[tuple[T, Awaitable[S]]], /):
    self._awaitable = awaitable

  def __await__(self):
    return self._awaitable.__await__()

  async def __aenter__(self):
    value, next_task = await self._awaitable

    async def func():
      await next_task

    self._contextualized = contextualize(func(), daemon=True)
    await self._contextualized.__aenter__()

    return value

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)


async def main():
  async with Handle(asyncio.sleep(1)):
    print("Handle is running")
    await asyncio.sleep(2)


asyncio.run(main())
