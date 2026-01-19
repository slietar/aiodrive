import asyncio
import functools
from asyncio import Future, Task
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Never, Optional

from ..internal.future import ensure_future
from .cancel import cancel_task
from .contextualize import contextualize
from .daemon import ensure_daemon


@dataclass(init=False, slots=True)
class DaemonHandle:
  """
  A class that manages the awaiting and cancellation of a daemon awaitable.

  The awaitable is wrapped as a task as soon as the `DaemonHandle` instance is
  created. It can be consumed in three ways:

  1. By awaiting the instance and employing an external cancellation mechanism.
  1. By using the instance as asynchronous context manager, where the task is
     cancelled when exiting. The current task is cancelled if an exception is
     raised by the handled task.
  1. By calling the `.aclose()` method, which cancels and then awaits the task.
     This can be delegated to the `contextlib.aclosing()` function to attach the
     task to a context manager. If using this option, the current task is not
     cancelled if an exception is raised by the handled task.
  """

  _contextualized: Optional[AbstractAsyncContextManager[None]] = field(default=None, repr=False)
  _task: Future[Never] = field(repr=False)

  def __init__(self, awaitable: Awaitable[Never], /):
    self._task = ensure_future(ensure_daemon(awaitable))

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
    if isinstance(self._task, Task):
      await cancel_task(self._task)
    else:
      self._task.cancel()


@dataclass(slots=True)
class PendingDaemonHandle[T]:
  """
  A class that manages the initialization, awaiting and cancellation of a daemon
  awaitable.

  This class handles an awaitable that first yields an intermediate value and
  then behaves like a daemon awaitable.
  """

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


def using_pending_daemon_handle[**P, T](func: Callable[P, AsyncGenerator[T]], /):
  """
  Decorate the provided function such that it returns a `PendingDaemonHandle`.
  """

  @functools.wraps(func)
  def new_func(*args: P.args, **kwargs: P.kwargs):
    generator = func(*args, **kwargs)

    async def first_call():
      try:
        value = await anext(generator)
      except StopAsyncIteration:
        raise RuntimeError('Generator should yield')

      return value, second_call()

    async def second_call():
      loop = asyncio.get_running_loop()

      try:
        await loop.create_future()
      except asyncio.CancelledError:
        try:
          await anext(generator)
        except StopAsyncIteration:
          pass
        else:
          try:
              raise RuntimeError('Generator did not stop')
          finally:
              await generator.aclose()

        raise

      # For the type checker
      raise RuntimeError('Unreachable')

    return PendingDaemonHandle(first_call())

  return new_func


__all__ = [
  'DaemonHandle',
  'PendingDaemonHandle',
  'using_pending_daemon_handle',
]
