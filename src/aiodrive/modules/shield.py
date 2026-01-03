import asyncio
from asyncio import Future
from collections.abc import Awaitable
from dataclasses import dataclass, field

from .future_state import FutureState


def shield[T](awaitable: Awaitable[T], /) -> Awaitable[T]:
  """
  Shield an awaitable from cancellation.

  This function is identical to `asyncio.shield()` but does not display
  exceptions raised by the inner future after shielding occured in Python 3.14
  and later.

  Parameters
  ----------
  awaitable
    The future to shield.

  Returns
  -------
  T
    The future's result.
  """

  inner = asyncio.ensure_future(awaitable)

  if inner.done():
    return inner

  outer = Future[T]()

  def inner_callback(_inner: Future[T]):
    if outer.cancelled():
      return

    FutureState.absorb_future(inner).transfer(outer)

  def outer_callback(_outer: Future[T]):
    inner.remove_done_callback(inner_callback)

  inner.add_done_callback(inner_callback)
  outer.add_done_callback(outer_callback)

  return outer


async def shield_wait[T](awaitable: Awaitable[T], /, *, shield_count: int = 1) -> T:
  """
  Shield and await an awaitable.

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


async def shield_wait_forever[T](awaitable: Awaitable[T], /) -> T:
  """
  Shield and await the an awaitable indefinitely, ignoring all cancellation
  requests.

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

    return await shield_wait(
      awaitable,
      shield_count=(shield_count - self._initial_cancellation_count),
    )


__all__ = [
  'ShieldContext',
  'shield',
  'shield_wait',
  'shield_wait_forever',
]
