import asyncio
from collections.abc import Awaitable, Callable
from contextvars import Context
from typing import Self


class GuaranteedTask[T]:
  """
  A variant of `asyncio.Task` that guarantees that the provided awaitable is
  awaited.
  """

  def __init__(self, awaitable: Awaitable[T], /) -> None:
    async def task_main():
      self._ready = True

      for _ in range(self._cancellation_count):
        self._task.cancel()

      await awaitable

    self._cancellation_count = 0
    self._ready = False
    self._task = asyncio.create_task(task_main())

  def add_done_callback(self, fn: Callable[[Self], object], /, *, context: Context | None = None):
    self._task.add_done_callback(lambda task: fn(self), context=context)

  def remove_done_callback(self, fn: Callable[[Self], object], /):
    self._task.remove_done_callback(lambda task: fn(self))

  def cancel(self):
    self._cancellation_count += 1

    if self._ready:
      self._task.cancel()

  def exception(self):
    return self._task.exception()

  def uncancel(self):
    if self._cancellation_count > 0:
      self._cancellation_count -= 1

      if self._ready:
        self._task.uncancel()

  def cancelling(self):
    return self._cancellation_count

  def cancelled(self):
    return self._task.cancelled()

  def done(self):
    return self._task.done()

  def __await__(self):
    return self._task.__await__()


__all__ = [
  'GuaranteedTask',
]
