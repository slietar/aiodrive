import contextlib
from asyncio import TaskGroup
from collections.abc import AsyncIterator

from .cancel import suppress


class TaskGroupTerminatedException(Exception):
  pass

@contextlib.asynccontextmanager
async def eager_task_group() -> AsyncIterator[TaskGroup]:
  """
  Create a `TaskGroup` that automatically terminates when the context is exited.
  """

  with suppress(TaskGroupTerminatedException):
    async with TaskGroup() as group:
      yield group
      raise TaskGroupTerminatedException


__all__ = [
  'eager_task_group',
]
