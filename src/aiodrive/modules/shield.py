import asyncio
from collections.abc import Awaitable


async def shield[T](awaitable: Awaitable[T], /, *, shield_count: int = 1) -> T:
  """
  Shield and then await the provided awaitable, taking into account existing
  cancellation requests.

  Parameters
  ----------
  awaitable
    The awaitable to shield and await.
  shield_count
    The number of times to shield the awaitable.

  Returns
  -------
  T
    The awaitable's result.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  rel_shield_count = shield_count - current_task.cancelling()

  if rel_shield_count <= 0:
    return await awaitable

  task = asyncio.ensure_future(awaitable)

  for _ in range(rel_shield_count):
    try:
      return await asyncio.shield(task)
    except asyncio.CancelledError:
      await task
      raise

  return await task


async def shield_forever[T](awaitable: Awaitable[T], /) -> T:
  """
  Shield and then await the provided awaitable forever, ignoring all
  cancellation requests.

  Parameters
  ----------
  awaitable
    The awaitable to shield and await.

  Returns
  -------
  T
    The awaitable's result.
  """

  cancelled = False
  task = asyncio.ensure_future(awaitable)

  while True:
    try:
      result = await asyncio.shield(task)
    except asyncio.CancelledError:
      cancelled = True
      continue

    if cancelled:
      raise asyncio.CancelledError

    return result


__all__ = [
  'shield',
  'shield_forever',
]
