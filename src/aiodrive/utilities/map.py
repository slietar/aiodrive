import contextlib
import itertools
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable
from typing import Optional

from .task_group import use_eager_task_group
from .button import Button
from .iterator import ensure_aiter
from .ordered_queue import OrderedQueue, UnorderedQueue


# TODO: Add option to select max queue size
# TODO: No queue --> let's create another utility for this


@contextlib.asynccontextmanager
async def map_parallel[T, S](
  mapper: Callable[[T], Awaitable[S]],
  iterable: AsyncIterable[T] | Iterable[T],
  /, *,
  max_concurrent_count: Optional[int] = None,
  ordered: bool,
) -> AsyncIterator[AsyncIterable[S]]:
  """
  Map an `Iterable` or `AsyncIterable` to another `AsyncIterable` using the
  provided asynchronous mapper function.

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
    ones.

  Returns
  -------
  AbstractAsyncContextManager[AsyncIterable[S]]
    An asynchronous context manager that provides an `AsyncIterable` of the
    mapped items. The context manager may only be used once and is necessary in
    order to clean up any pending item processing.
  """

  button = Button()
  queue = OrderedQueue[S]() if ordered else UnorderedQueue[S]()

  closed = False
  running_count = 0
  iterator = ensure_aiter(iterable)

  async def run(index: int, item: T):
    nonlocal running_count

    try:
      queue.put(index, await mapper(item))
    finally:
      button()
      running_count -= 1

  async def put_queue():
    nonlocal closed, running_count

    for index in itertools.count():
      # TODO: Problem, the same index may be used for multiple items

      while (max_concurrent_count is None) or (running_count < max_concurrent_count):
        try:
          item = await anext(iterator)
        except StopAsyncIteration:
          closed = True
          return
        else:
          group.create_task(run(index, item))
          running_count += 1

      await button

  async with use_eager_task_group() as group:
    group.create_task(put_queue())

    async def create_iter():
      while (not closed) or (running_count > 0) or not queue.empty():
        yield await queue.get()

    yield create_iter()
