import asyncio
import contextlib
from collections.abc import Awaitable

from .cancel import cancel_task
from .guaranteed_task import GuaranteedTask
from .scope import use_scope


@contextlib.asynccontextmanager
async def contextualize(awaitable: Awaitable[None], /):
  """
  Transform an awaitable into an asynchronous context manager.

  When the context is exited, the background task created from the awaitable is
  cancelled and awaited, if still running. If the background task raises an
  exception, the current task is cancelled until exiting the context. If both
  the current and background tasks raise an exception, the exceptions are
  aggregated into an `ExceptionGroup`.

  Exceptions are reported in a `BaseExceptionGroup` only if both the background
  task and the current task raised exceptions.

  Parameters
  ----------
  awaitable
    The awaitable to run in the background. If the returned context manager is
    entered, it is awaited exactly once, and it is otherwise awaited at most
    once.

  Returns
  -------
  AbstractAsyncContextManager[None]
    An async context manager that runs the given awaitable in the background.
  """

  background_task = GuaranteedTask(awaitable)

  def callback(task: GuaranteedTask[None]):
    # If the background task finished with an exception, cancel the scope.
    if not task.cancelled() and (task.exception() is not None):
      scope.cancel()

  background_task.add_done_callback(callback)

  try:
    with use_scope() as scope:
      yield
  except asyncio.CancelledError:
    background_task.remove_done_callback(callback)

    # One of the following is possible:
    #   (1) The origin task is being cancelled by the user.
    #   (2) The background task raised an exception, which caused the origin task
    #     to be cancelled.

    # In case (2), this will re-raise the exception from the background task.
    await cancel_task(background_task)

    # In case (1), this will re-raise the CancelledError.
    raise
  except BaseException as e:
    background_task.remove_done_callback(callback)

    try:
      await cancel_task(background_task)
    except BaseException as background_task_exception:
      raise BaseExceptionGroup("", [e, background_task_exception]) from None

    raise
  else:
    background_task.remove_done_callback(callback)
    await cancel_task(background_task)


__all__ = [
  'contextualize',
]
