from asyncio import Task
import asyncio
from typing import Any, Awaitable, TypeVar


async def cancel_task(task: Task[Any], /):
  """
  Silently cancel and then await the provided task, if any.

  The task is cancelled and then awaited. The `asyncio.CancelledError` instance raised by the task is ignored.

  Parameters
    task: The task to cancel, or `None`.
  """

  task.cancel()

  try:
    await task
  except asyncio.CancelledError:
    task.uncancel()


async def shield[T](awaitable: Awaitable[T], /) -> T:
  """
  Shield and then await the provided awaitable from cancellation.

  The provided awaitable is wrapped in a task and then awaited with `asyncio.shield()`. If the call to `shield()` is cancelled, the task is awaited again and the exception is then re-raised. If the call is cancelled again, the task is cancelled without shielding.

  Returns
    The task's result, assuming no cancellation occurs.

  Raises
    asyncio.CancelledError: If the call to `shield()` is cancelled and after the task finishes.
  """

  task = asyncio.ensure_future(awaitable)

  try:
    return await asyncio.shield(task)
  except asyncio.CancelledError:
    await task
    raise


__all__ = [
  'cancel_task',
  'shield'
]
