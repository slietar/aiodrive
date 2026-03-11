import asyncio
from collections.abc import Awaitable, Iterable

from ..internal.future import ensure_future
from ..internal.sized import (
  CloseableSizedAsyncIterator,
  sized_aiterator,
)
from .gather import gather


# TODO: Add max_concurrent_count


def amass[T](awaitables: Iterable[Awaitable[T]], /, *, sensitive: bool = True) -> CloseableSizedAsyncIterator[T]:
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

  tasks = [ensure_future(awaitable) for awaitable in awaitables]

  async def generator():
    cancelled = False
    pending_tasks = set(tasks)

    try:
      while pending_tasks:
        try:
          done_tasks, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
          cancelled = True
          return

        for task in done_tasks:
          try:
            result = task.result()
          except:  # noqa: E722
            if sensitive:
              return
          else:
            yield result
    finally:
      for task in pending_tasks:
        task.cancel()

      await gather(tasks, sensitive=False)

    if cancelled:
      raise asyncio.CancelledError

  return sized_aiterator(generator(), length=len(tasks)) # type: ignore


__all__ = [
  'amass',
]
