import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field


async def shield[T](awaitable: Awaitable[T], /, *, shield_count: int = 1) -> T:
  """
  Shield and await a given awaitable.

  Parameters
  ----------
  awaitable
    The awaitable to shield and await.
  shield_count
    The number of times to shield the awaitable. A negative value is treated as
    zero.

  Returns
  -------
  T
    The awaitable's result.
  """

  if shield_count <= 0:
    return await awaitable

  task = asyncio.ensure_future(awaitable)

  for _ in range(shield_count):
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


@dataclass(slots=True)
class ShieldContext:
  """
  A class for shielding awaitables from cancellation based on the cancellation
  request count at the time of instantiation.
  """

  _initial_cancellation_count: int = field(repr=False)

  def __init__(self):
    current_task = asyncio.current_task()
    assert current_task is not None

    self._initial_cancellation_count = current_task.cancelling()

  async def shield[T](self, awaitable: Awaitable[T], /, *, shield_count: int = 1) -> T:
    """
    Shield and await a given awaitable, taking into account the existing
    cancellation request count at the time of instantiation.

    Parameters
    ----------
    awaitable
      The awaitable to shield and await.
    shield_count
      The number of times to shield the awaitable. A negative value is treated
      as zero.

    Returns
    -------
    T
      The awaitable's result.
    """

    return await shield(
      awaitable,
      shield_count=(shield_count - self._initial_cancellation_count),
    )


__all__ = [
  'ShieldContext',
  'shield',
  'shield_forever',
]
