from asyncio import Task
from collections.abc import Awaitable
from typing import Any, Optional, override


class GuaranteedTask[T](Task[T]):
  """
  A variant of `asyncio.Task` that guarantees that the provided awaitable is
  awaited before any cancellation occurs.
  """

  def __init__(self, awaitable: Awaitable[T], /) -> None:
    async def task_main():
      self.__ready = True

      for _ in range(self.__cancellation_count):
        parent.cancel()

      return await awaitable

    parent = super()
    parent.__init__(task_main())

    self.__cancellation_count = 0
    self.__ready = False

  @override
  def cancel(self, msg: Optional[Any] = None):
    if self.cancelled():
      return False

    self.__cancellation_count += 1

    if self.__ready:
      super().cancel()

    return True

  @override
  def uncancel(self):
    if self.__cancellation_count > 0:
      self.__cancellation_count -= 1

      if self.__ready:
        super().uncancel()

    return self.__cancellation_count

  @override
  def cancelling(self):
    return self.__cancellation_count


__all__ = [
  'GuaranteedTask',
]
