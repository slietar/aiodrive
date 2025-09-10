import asyncio
import contextlib
from asyncio import Task
from collections.abc import Awaitable

from .cancel import cancel_task
from .guaranteed_task import GuaranteedTask
from .scope import use_scope


class DaemonTaskFinishError(Exception):
  __slots__ = ()


@contextlib.asynccontextmanager
async def contextualize(awaitable: Awaitable[None], /, *, daemon: bool = False):
  """
  Transform an awaitable into an async context manager.

  When the context is exited, the background task created from the awaitable is
  cancelled and awaited, if still running. If the background task raises an
  exception, the current task is cancelled until exiting the context. If both
  the current and background tasks raise an exception, the exceptions are
  aggregated into an `ExceptionGroup`.

  Parameters
  ----------
  awaitable
    The awaitable to run in the background.
  daemon
    Whether the awaitable should run forever until cancelled.

  Raises
  ------
  DaemonTaskFinishError
    If `daemon` is `True` and the background task finishes successfully before
    being cancelled.
  """

  if daemon:
    async def create_target():
      await awaitable
      raise DaemonTaskFinishError

    target = create_target()
  else:
    target = awaitable

  background_task = GuaranteedTask(target)

  def callback(task: Task[None]):
    if not task.cancelled() and (task.exception() is not None):
      scope.cancel()

  background_task.add_done_callback(callback)

  try:
    async with use_scope() as scope:
      yield
  except asyncio.CancelledError:
    background_task.remove_done_callback(callback)

    # One of the following is possible:
    #   - The origin task is being cancelled by the user.
    #   - The background task raised an exception, which caused the origin task
    #     to be cancelled.

    await cancel_task(background_task)
    raise
  except Exception as e:
    background_task.remove_done_callback(callback)

    try:
      await cancel_task(background_task)
    except Exception as background_task_exception:
      raise ExceptionGroup("", [e, background_task_exception]) from None

    raise
  else:
    background_task.remove_done_callback(callback)
    await cancel_task(background_task)


__all__ = [
  'DaemonTaskFinishError',
  'contextualize',
]
