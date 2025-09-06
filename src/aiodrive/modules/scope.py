import asyncio
import contextlib
from asyncio import Task
from dataclasses import dataclass, field


@dataclass(slots=True)
class Scope:
  cancellation_count: int = field(default=0, init=False)
  task: Task = field(repr=False)

  def cancel(self):
    """
    Cancel the current task.

    The current task will be uncancelled once the scope is exited.
    """

    self.task.cancel()
    self.cancellation_count += 1


@contextlib.asynccontextmanager
async def use_scope():
  """
  Create a context that locally manages the cancellation of the current task.
  """

  task = asyncio.current_task()
  assert task is not None

  scope = Scope(task)

  try:
    yield scope
  except asyncio.CancelledError:
    for _ in range(scope.cancellation_count):
      task.uncancel()

    if task.cancelling() != 0:
      raise


__all__ = [
  'Scope',
  'use_scope',
]
