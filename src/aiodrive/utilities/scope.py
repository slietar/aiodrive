import asyncio
import contextlib
from asyncio import Task
from dataclasses import dataclass, field


@dataclass(slots=True)
class Scope:
  cancellation_count: int = field(default=0, init=False)
  task: Task = field(repr=False)

  def cancel(self):
    self.task.cancel()


@contextlib.asynccontextmanager
async def use_scope():
  task = asyncio.current_task()
  assert task is not None

  scope = Scope(task)

  try:
    yield scope
  except asyncio.CancelledError:
    for _ in range(scope.cancellation_count):
      task.uncancel()

    # TODO: Maybe using task.cancelled() is ok
    if task.cancelling() != 0:
      raise
