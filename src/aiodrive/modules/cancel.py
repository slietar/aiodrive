import asyncio
import contextlib
from asyncio import Task


async def cancel_task(task: Task[object], /):
  """
  Cancel and await the provided task.

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


def ensure_correct_cancellation():
  """
  Raise a `CancelledError` if the current task was cancelled.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  if current_task.cancelling() > 0:
    raise asyncio.CancelledError


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
    yield
  except* exceptions:
    pass
  else:
    if strict:
      raise SuppressFailureError('No exception to suppress')

  try:
    current_task = asyncio.current_task()
  except RuntimeError:
    pass
  else:
    if current_task is not None:
      ensure_correct_cancellation()


__all__ = [
  'SuppressFailureError',
  'cancel_task',
  'ensure_correct_cancellation',
  'suppress',
]
