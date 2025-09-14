import asyncio
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

      if task.cancelling() > 1:
        raise


__all__ = [
  'cancel_task',
]
