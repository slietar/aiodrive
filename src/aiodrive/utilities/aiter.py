from collections import deque
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Optional

from .latch import Latch
from .versatile import contextualize


async def buffer_aiter[T](iterable: AsyncIterable[T], /, *, size: Optional[int]):
  """
  Create an async generator that prefetches items from the given async iterable.

  Items are prefetched sequentially from the iterable. It is crucial for the
  returned generator to be closed in order for any remaining the prefetching
  task to be cancelled.

  Parameters
  ----------
  iterable
    The async iterable to prefetch items from.
  size
    The maximum number of items to prefetch. If `None`, there is no limit.

  Yields
  ------
  T
    Items from the given async iterable.
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
