import asyncio
from collections.abc import Awaitable


async def shield[T](awaitable: Awaitable[T], /) -> T:
  """
  Shield and then await the provided awaitable.

  Parameters
  ----------
  awaitable
    The awaitable to shield and await.

  Returns
  -------
  T
    The awaitable's result.
  """

  task = asyncio.ensure_future(awaitable)

  try:
    return await asyncio.shield(task)
  except asyncio.CancelledError:
    await task
    raise


async def cleanup_shield[T](awaitable: Awaitable[T], /) -> T:
  """
  Await the provided awaitable, shielding it if the current task has not been
  already cancelled.

  Returns
  -------
  T
    The awaitable's result.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  if current_task.cancelling() > 0:
    return await awaitable

  return await shield(awaitable)


__all__ = [
  'cleanup_shield',
  'shield',
]
