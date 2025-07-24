from asyncio import Event, Future
import asyncio
from collections.abc import Awaitable, Callable

from .transfer_future import transfer_future


class BatchWorker[K, R]:
  """
  A utility class to batch an operation.

  Batched items are pushed to the batch queue. using `write()`. If there is no
  batch currently being committed, all items in the batch queue are committed by
  providing a list to the committer function. If all writes are cancelled, the
  committer function is not called, or cancelled if is already running. The
  committer function returns a list of results, which are returned to the
  corresponding `write()` calls.
  """

  def __init__(self, commit: Callable[[list[K]], Awaitable[list[R]]], *, dispatch_exceptions: bool = False):
    self._commit = commit
    self._dispatch_exceptions = dispatch_exceptions

    self._futures = dict[int, Future[R]]()
    self._items = dict[int, K]()
    self._next_item_index = 0
    self._write_event = Event()

  async def start(self):
    while True:
      await self._write_event.wait()
      self._write_event.clear()

      indices = list(self._items.keys())
      items = list(self._items.values())
      self._items.clear()

      futures = [self._futures[index] for index in indices]
      commit_task = asyncio.ensure_future(self._commit(items))

      end_index, _ = await race(
        (suppress(commit_task) if self._dispatch_exceptions else commit_task),
        asyncio.wait(futures)
      )

      if end_index == 0:
        for result_index, write_index in enumerate(indices):
          future = self._futures.get(write_index)

          if future:
            transfer_future(commit_task, future, transform=(lambda result: result[result_index]))

  async def write(self, item: K, /):
    item_index = self._next_item_index
    self._next_item_index += 1

    self._items[item_index] = item
    self._write_event.set()

    future = Future[R]()
    self._futures[item_index] = future

    try:
      return await future
    except asyncio.CancelledError:
      # If not being written yet
      if item_index in self._items:
        del self._items[item_index]

      raise
    finally:
      del self._futures[item_index]
