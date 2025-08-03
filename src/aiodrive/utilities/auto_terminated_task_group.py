import contextlib
from asyncio import TaskGroup
from collections.abc import AsyncIterator


class TaskGroupTerminatedException(Exception):
  pass

@contextlib.asynccontextmanager
async def auto_terminated_task_group() -> AsyncIterator[TaskGroup]:
  """
  Create a `TaskGroup` that automatically terminates when the context is exited.
  """

  try:
    async with TaskGroup() as group:
      yield group
      raise TaskGroupTerminatedException
  except* TaskGroupTerminatedException:
    pass
