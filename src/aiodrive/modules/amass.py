import asyncio
from asyncio import Future
from collections.abc import Awaitable, Iterable, Sized
from typing import Optional

from .awaitable import terminate

from ..internal.future import ensure_future
from ..internal.sized import (
  CloseableSizedAsyncIterator,
  aiterator_impl,
)
from .gather import gather


def amass[T](
  awaitables: Iterable[Awaitable[T]],
  /, *,
  max_concurrent_count: Optional[int] = None,
  sensitive: bool = True,
) -> CloseableSizedAsyncIterator[T]:
  """
  Create an asynchronous iterator that yields results from awaitables as they
  complete.

  It is crucial to close the iterator for internal tasks to be cleaned up.

  This function is similar to `asyncio.as_completed()` but provides better
  cancellation behavior.

  Parameters
  ----------
  awaitables
    The awaitables to wait for, as multiple arguments or as an iterable.
  max_concurrent_count
    The maximum number of awaitables to run concurrently. If `None`, there is no
    limit and all awaitables are awaited immediately. If not `None` and the
    generator is closed while some awaitables have not yet been awaited, those
    awaitables are terminated.
  sensitive
    Whether to stop yielding results as soon as an exception is raised by one of
    the awaitables. If `True` and if a successful and a failed awaitable both
    finish during the same iteration of the event loop, it is unspecified
    whether the result is yielded before the exception is raised.

  Yields
  ------
  T
    Results from the provided awaitables as they complete.

  Raises
  ------
  BaseExceptionGroup
    If an awaitable raises an exception.
  """

  # tasks = [ensure_future(awaitable) for awaitable in awaitables]
  # pending_tasks = set(tasks)

  async def generator():
    cancelled = False
    awaitables_iter = iter(awaitables)

    all_futures = set[Future]()
    pending_futures = set[Future]()

    try:
      while True:
        while (max_concurrent_count is None) or (len(pending_futures) < max_concurrent_count):
          try:
            awaitable = next(awaitables_iter)
          except StopIteration:
            break

          future = ensure_future(awaitable)

          all_futures.add(future)
          pending_futures.add(future)

        if not pending_futures:
          break

        try:
          done_futures, pending_futures = await asyncio.wait(
            pending_futures,
            return_when=asyncio.FIRST_COMPLETED,
          )
        except asyncio.CancelledError:
          cancelled = True
          return

        for future in done_futures:
          try:
            result = future.result()
          except:  # noqa: E722
            if sensitive:
              return
          else:
            yield result
    finally:
      for future in pending_futures:
        future.cancel('Amass iterator closing')

      for awaitable in awaitables_iter:
        all_futures.add(ensure_future(terminate(awaitable)))

      await gather(all_futures, sensitive=False)

    if cancelled:
      raise asyncio.CancelledError

  return aiterator_impl(
    generator(),
    length=(len(awaitables) if isinstance(awaitables, Sized) else None),
  ) # type: ignore


__all__ = [
  'amass',
]
