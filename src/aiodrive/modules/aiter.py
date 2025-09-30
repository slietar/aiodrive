from collections import deque
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Optional

from .contextualize import contextualize
from .latch import Latch


async def buffer_aiter[T](iterable: AsyncIterable[T], /, *, size: Optional[int]):
  """
  Create an async generator that prefetches items from the given async iterable.

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
  Create an async iterator from the provided sync or async iterable.

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


__all__ = [
  'buffer_aiter',
  'collect',
  'ensure_aiter',
]
