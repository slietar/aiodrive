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
      If the scope has been exited.
    """

    if self.task is None:
      raise RuntimeError("Scope has already been exited")

    self.task.cancel()
    self.cancellation_count += 1


@contextlib.asynccontextmanager
async def use_scope_old():
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


@dataclass(slots=True)
class ScopeToken:
  _cancellation_count: int = field(default=0, init=False)
  _exited: bool = field(default=False, init=False)
  _task: Task = field(repr=False)

  def cancel(self):
    if self._exited:
      raise RuntimeError("Cannot cancel scope after it has exited")

    self._task.cancel()
    self._cancellation_count += 1

@dataclass(slots=True)
class use_scope_new:
  """
  Create a context that locally manages the cancellation of the current task.
  """

  _token: Optional[ScopeToken] = field(default=None, init=False, repr=False)

  async def __aenter__(self):
    assert self._token is None

    current_task = asyncio.current_task()
    assert current_task is not None

    self._token = ScopeToken(current_task)
    return self._token

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    assert self._token is not None
    self._token._exited = True

    try:
      if (exc_type is None) or not issubclass(exc_type, asyncio.CancelledError):
        return False

      for _ in range(self._token._cancellation_count):
        self._token._task.uncancel()

      if self._token._task.cancelling() != 0:
        return False

      return True
    finally:
      self._token = None


# use_scope = use_scope_new
use_scope = use_scope_old

__all__ = [
  'Scope',
  'use_scope',
]
