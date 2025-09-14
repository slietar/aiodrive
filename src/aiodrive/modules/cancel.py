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


@contextlib.contextmanager
def suppress(*exceptions: type[BaseException]):
  """
  Suppress the specified exceptions in an async context.

  Unlike `contextlib.suppress`, this context manager also ensures that if the
  current task was cancelled while inside the context, a `CancelledError` is
  re-raised upon exiting the context.

  Despite being synchronous, this function may only be used while in an event
  loop.

  Parameters
  ----------
  exceptions
    The exception types to suppress.
  """

  with contextlib.suppress(*exceptions):
    yield

  ensure_correct_cancellation()


__all__ = [
  'cancel_task',
  'ensure_correct_cancellation',
  'suppress',
]
