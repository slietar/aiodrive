from collections import deque
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from typing import Any, Optional, cast, overload

from .contextualize import contextualize
from .latch import Latch


async def buffer_aiter[T](iterable: AsyncIterable[T], /, *, size: Optional[int]):
  """
  Create an asynchronous generator that prefetches items from the given async
  iterable.

  Items are prefetched sequentially from the iterable. The current task is
  cancelled if the iterable raises an exception.

  Parameters
  ----------
  iterable
    The async iterable to prefetch items from.
  size
    The maximum number of items to prefetch. If `None`, there is no limit.

  Returns
  ------
  Generator[T]
    An asynchronous generator yielding the prefetched items. It is crucial to
    close the generator for internal tasks to be cleaned up.
  """

  iterator = aiter(iterable)
  queue = deque[T]()
  latch = Latch()

  async def producer():
    while True:
      if (size is not None) and (len(queue) >= size):
        await latch.wait_unset()

      queue.append(await anext(iterator))
      latch.set()

  async with contextualize(producer()):
    await latch.wait_set()
    item = queue.popleft()

    if not queue:
      latch.unset()

    yield item


async def collect[T](iterable: AsyncIterable[T], /):
  """
  Collect all items from the given async iterable into a list.

  Parameters
  ----------
  iterable
    The async iterable to collect items from.

  Returns
  -------
  list[T]
    A list containing all items from the iterable.
  """

  return [item async for item in iterable]


def ensure_aiter[T](iterable: AsyncIterable[T] | Iterable[T], /) -> AsyncIterator[T]:
  """
  Create an asynchronous iterator from the provided synchrounous or asynchronous
  iterable.

  Parameters
  ----------
  iterable
    The sync or async iterable to transform.

  Returns
  -------
  AsyncIterator[T]
    The created async iterator.
  """

  if hasattr(iterable, "__aiter__"):
    return aiter(iterable)  # type: ignore
  else:
    async def create_aiter():
      for item in iterable:  # type: ignore
        yield item

    return create_aiter()


initial_missing = object()

@overload
async def reduce[T](reducer: Callable[[T, T], T], iterable: AsyncIterable[T], /):
  ...

@overload
async def reduce[T, S](function: Callable[[S, T], S], iterable: AsyncIterable[T], /, initial: S):
  ...

async def reduce[T, S](function: Callable[[S, T], S], iterable: AsyncIterable[T], /, initial: S = cast(Any, initial_missing)):
  """
  Reduce the items from the provided asynchronous iterable.

  Parameters
  ----------
  function
    The reduction function taking the accumulator and the next item.
  iterable
    The async iterable to reduce.
  initial
    The initial value for the accumulator. If not provided, the iterable must
    have at least one item, which is used as the initial accumulator.

  Returns
  -------
  S
    The final accumulated value.
  """
  iterator = aiter(iterable)

  if initial is not initial_missing:
    accumulator = initial
  else:
    try:
      accumulator = await anext(iterator)
    except StopAsyncIteration as e:
      raise TypeError("Cannot reduce empty sequence with no initial value") from e

    accumulator = cast(S, accumulator)

  async for item in iterator:
    accumulator = function(accumulator, item)

  return accumulator


__all__ = [
  'buffer_aiter',
  'collect',
  'ensure_aiter',
  'reduce',
]
