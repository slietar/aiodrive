from collections.abc import AsyncIterable, Awaitable, Callable, Iterable, Sized
from typing import Optional, overload

from ..internal.queue import OrderedQueue, UnorderedQueue
from ..internal.sized import (
  CloseableAsyncIterable,
  CloseableSizedAsyncIterable,
  SizedAsyncIterable,
  SizedIterable,
  sized_aiter,
)
from .aiter import ensure_aiter
from .task_group import volatile_task_group


@overload
def map[T, S](
  mapper: Callable[[T], Awaitable[S]],
  iterable: SizedAsyncIterable[T] | SizedIterable[T],
  /, *,
  max_concurrent_count: Optional[int] = ...,
  ordered: bool,
) -> CloseableSizedAsyncIterable[S]:
  ...

@overload
def map[T, S](
  mapper: Callable[[T], Awaitable[S]],
  iterable: AsyncIterable[T] | Iterable[T],
  /, *,
  max_concurrent_count: Optional[int] = ...,
  ordered: bool,
) -> CloseableAsyncIterable[S]:
  ...

def map[T, S](
  mapper: Callable[[T], Awaitable[S]],
  iterable: AsyncIterable[T] | Iterable[T],
  /, *,
  max_concurrent_count: Optional[int] = None,
  ordered: bool,
) -> CloseableAsyncIterable[S] | CloseableSizedAsyncIterable[S]:
  """
  Map an `Iterable` or `AsyncIterable` to an `AsyncIterable` using the given
  asynchronous mapper function.

  Parameters
  ----------
  mapper
    The asynchronous function to apply to each item in the iterable.
  iterable
    The iterable or asynchronous iterable to map over.
  max_concurrent_count
    The maximum number of concurrent tasks to run. If `None`, all items are
    processed as soon as they are received from the iterable. In particular, if
    the iterable is synchronous, they are processed immediately. Must be at
    least 1.
  ordered
    Whether to maintain the order of items in the output. If false, items may be
    yielded more quickly if some later items are processed faster than earlier
    ones. However, items are still yielded in the order in which they are
    returned by the mapper.

  Returns
  -------
  Generator[S]
    An asynchronous generator yielding the mapped items. It is crucial to close
    the generator for internal tasks to be cleaned up.
  """

  assert (max_concurrent_count is None) or (max_concurrent_count >= 1)

  async def generator():
    queue = OrderedQueue[S]() if ordered else UnorderedQueue[S]()

    iterator = ensure_aiter(iterable)
    job_count = 0

    async def job():
      nonlocal job_count

      try:
        item = await anext(iterator)
      except StopAsyncIteration:
        queue.close()
      else:
        if (max_concurrent_count is None) or (job_count < max_concurrent_count):
          group.create_task(job())
          job_count += 1

        put_item = queue.reserve()
        put_item(await mapper(item))
      finally:
        job_count -= 1

    async with volatile_task_group() as group:
      group.create_task(job())
      job_count += 1

      async for mapped_item in queue:
        yield mapped_item

  if isinstance(iterable, Sized):
    length = len(iterable)
  else:
    length = None

  return sized_aiter(generator(), length=length)


__all__ = [
  'map',
]
