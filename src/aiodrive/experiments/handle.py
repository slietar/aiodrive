import asyncio
from asyncio import Task
from collections.abc import Awaitable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Never, Optional

from ..modules.cancel import cancel_task
from ..modules.contextualize import contextualize


@dataclass(init=False, slots=True)
class Handle:
  """
  A class used to manage the awaiting and cancellation of an awaitable that
  never returns.

  The awaitable is wrapped as a task as soon as the `Handle` instance is
  created. It can be consumed in three ways:

  1. By awaiting the instance and employing an external cancellation mechanism.
  1. By using the instance as asynchronous context manager, where the task is
     cancelled when exiting.
  1. By calling the `.aclose()` method, which cancels and then awaits the task.
     This can be delegated to the `contextlib.aclosing()` function to attach the
     task to a context manager. If using the option, the current task is not
     cancelled if an exception is raised by the handled task.
  """

  _contextualized: Optional[AbstractAsyncContextManager[None]] = field(default=None, repr=False)
  _task: Task[Never] = field(repr=False)

  def __init__(self, awaitable: Awaitable[Never], /):
    self._task = asyncio.ensure_future(awaitable)

  def __await__(self):
    return self._task.__await__()

  async def __aenter__(self):
    async def func():
      await self._task

    assert self._contextualized is not None
    self._contextualized = contextualize(func())
    await self._contextualized.__aenter__()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    assert self._contextualized is not None
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)

  async def aclose(self):
    await cancel_task(self._task)


class PendingHandle[T]:
  def __init__(self, awaitable: Awaitable[tuple[T, Awaitable[Never]]], /):
    self._awaitable = awaitable

  async def __aenter__(self):
    value, next_awaitable = await self._awaitable

    async def func():
      await next_awaitable

    self._contextualized = contextualize(func(), daemon=True)
    await self._contextualized.__aenter__()

    return value

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)


async def main():
  async def a():
    while True:
      pass

  async with Handle(a()):
    print("Handle is running")
    await asyncio.sleep(2)


asyncio.run(main())
