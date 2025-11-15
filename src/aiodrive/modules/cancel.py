import asyncio
import contextlib
from asyncio import Task


async def cancel_task(task: Task[object], /):
  """
  Cancel and await the provided task.

  If raised, the `asyncio.CancelledError` exception is suppressed.

  Parameters
  ----------
  task
    The task to cancel.
  """

  if task.done():
    await task
  else:
    task.cancel()

    try:
      await task
    except asyncio.CancelledError:
      task.uncancel()

      if task.cancelling() > 0:
        raise


class SuppressFailureError(RuntimeError):
  pass

@contextlib.contextmanager
def suppress(*exceptions: type[BaseException], strict: bool = False):
  """
  Suppress the specified exceptions in an async context.

  Unlike `contextlib.suppress`, this context manager ensures that, if there is a
  running event loop and the current task was cancelled while inside the
  context, a `CancelledError` is re-raised upon exiting the context.

  Parameters
  ----------
  exceptions
    The exception types to suppress.
  strict
    Whether to raise an exception if no exceptions were suppressed.

  Raises
  ------
  SuppressFailureError
    If `strict` is `True` and no exceptions were suppressed.
  """

  try:
    current_task = asyncio.current_task()
  except RuntimeError:
      cancellation_count = None
  else:
    if current_task is not None:
      cancellation_count = current_task.cancelling()
    else:
      cancellation_count = None

  try:
    yield
  except* exceptions:
    pass
  else:
    if strict:
      raise SuppressFailureError('No exception to suppress')

  if cancellation_count is not None:
    current_task = asyncio.current_task()
    assert current_task is not None

    if current_task.cancelling() > cancellation_count:
      raise asyncio.CancelledError


__all__ = [
  'SuppressFailureError',
  'cancel_task',
  'suppress',
]
