import asyncio
import contextlib
from asyncio import Task

from .event_loop import get_event_loop


async def cancel_task(task: Task[object], /):
  """
  Cancel and await the provided task.

  If raised, the `CancelledError` exception is suppressed.

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


@contextlib.contextmanager
def ensure_correct_cancellation():
  """
  Ensure that a `CancelledError` is raised if the current task was cancelled
  while inside the context.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  initial_cancellation_count = current_task.cancelling()

  yield

  if current_task.cancelling() > initial_cancellation_count:
    raise asyncio.CancelledError from None


class SuppressFailureError(RuntimeError):
  pass

@contextlib.contextmanager
def suppress(*exceptions: type[BaseException], strict: bool = False):
  """
  Suppress the specified exceptions in an asynchronous context.

  Unlike `contextlib.suppress()`, this context manager ensures that, if there is a
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

  with (
    ensure_correct_cancellation()
    if get_event_loop() is not None
    else contextlib.nullcontext()
  ):
    try:
      yield
    except* exceptions:
      pass
    else:
      if strict:
        raise SuppressFailureError('No exception to suppress')


__all__ = [
  'SuppressFailureError',
  'cancel_task',
  'ensure_correct_cancellation',
  'suppress',
]
