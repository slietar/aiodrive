from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from typing import Optional

from ..modules.aiter import ensure_aiter
from ..modules.task_group import volatile_task_group
from .ordered_queue import OrderedQueue, UnorderedQueue


async def map_parallel[T, S](
  mapper: Callable[[T], Awaitable[S]],
  iterable: AsyncIterable[T] | Iterable[T],
  /, *,
  max_concurrent_count: Optional[int] = None,
  ordered: bool,
):
  """
  Map an `Iterable` or `AsyncIterable` to another `AsyncIterable` using a given
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
    the iterable is synchronous, they are processed immediately.
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



# exhausted
