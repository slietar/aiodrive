import contextlib
from asyncio import TaskGroup
from collections.abc import AsyncIterator

from .cancel import suppress


class TaskGroupTerminatedException(Exception):
  pass

@contextlib.asynccontextmanager
async def volatile_task_group() -> AsyncIterator[TaskGroup]:
  """
  Create a `TaskGroup` that automatically terminates when exiting the context.

  Returns
  -------
  AbstractAsyncContextManager[TaskGroup]
  """

  with suppress(TaskGroupTerminatedException):
    async with TaskGroup() as group:
      yield group
      raise TaskGroupTerminatedException


__all__ = [
  'volatile_task_group',
]
