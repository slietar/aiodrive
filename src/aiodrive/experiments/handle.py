import asyncio
import functools
from asyncio import Task
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Never, Optional

from ..modules.cancel import cancel_task
from ..modules.contextualize import contextualize
from ..modules.daemon import ensure_daemon


@dataclass(init=False, slots=True)
class DaemonHandle:
  """
  A class that manages the awaiting and cancellation of a daemon awaitable.

  The awaitable is wrapped as a task as soon as the `DaemonHandle` instance is
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
    self._task = asyncio.ensure_future(ensure_daemon(awaitable))

  def __await__(self):
    return self._task.__await__()

  async def __aenter__(self):
    assert self._contextualized is not None
    self._contextualized = contextualize(self._task)
    await self._contextualized.__aenter__()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    assert self._contextualized is not None
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)

  async def aclose(self):
    await cancel_task(self._task)


@dataclass(slots=True)
class PendingHandle[T]:
  _awaitable: Awaitable[tuple[T, Awaitable[Never]]] = field(repr=False)
  _contextualized: Optional[AbstractAsyncContextManager[None]] = field(default=None, init=False, repr=False)

  async def start(self):
    value, daemon_awaitable = await self._awaitable
    return value, DaemonHandle(daemon_awaitable)

  async def __aenter__(self):
    value, daemon_awaitable = await self._awaitable

    assert self._contextualized is None
    self._contextualized = contextualize(ensure_daemon(daemon_awaitable))
    await self._contextualized.__aenter__()

    return value

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    assert self._contextualized is not None
    return await self._contextualized.__aexit__(exc_type, exc_value, traceback)


def using_pending_handle[**P, T](func: Callable[P, AsyncIterator[T]], /):
  @functools.wraps(func)
  def new_func(*args: P.args, **kwargs: P.kwargs):
    iterator = aiter(func(*args, **kwargs))

    async def first_call():
      try:
        value = await anext(iterator)
      except StopAsyncIteration:
        raise RuntimeError('Generator should yield')

      return value, second_call()

    async def second_call():
      try:
        await anext(iterator)
      except StopAsyncIteration:
        raise RuntimeError('Generator should not return')
      else:
        raise RuntimeError('Generator should not yield')

    return PendingHandle(first_call())

  return new_func


async def main():
  @using_pending_handle
  async def a():
    yield 24

    try:
      await asyncio.Future()
    finally:
      print("Cleaning up")

  x = a()

  async with x as y:
    print("Handle is running", y)
    await asyncio.sleep(.5)

  print("Done")


asyncio.run(main())
