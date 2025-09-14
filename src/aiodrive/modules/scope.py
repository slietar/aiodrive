import asyncio
import contextlib
from asyncio import Task
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Scope:
  cancellation_count: int = field(default=0, init=False)
  task: Optional[Task] = field(repr=False)

  def cancel(self):
    """
    Cancel the current task.

    The current task is uncancelled once the scope is exited.

    Raises
    ------
    RuntimeError
      If the scope has already been exited.
    """

    if self.task is None:
      raise RuntimeError("Scope has already been exited")

    self.task.cancel()
    self.cancellation_count += 1


@contextlib.contextmanager
def use_scope():
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
  finally:
    scope.task = None


__all__ = [
  'Scope',
  'use_scope',
]
