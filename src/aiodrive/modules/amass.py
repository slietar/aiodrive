import asyncio
from collections.abc import Awaitable, Iterable

from .gather import gather


async def amass[T](awaitables: Iterable[Awaitable[T]], /, *, sensitive: bool = True):
  """
  Create an asynchronous iterator that yields results from awaitables as they
  complete.

  It is crucial to close the generator for internal tasks to be cleaned up.

  Parameters
  ----------
  awaitables
    The awaitables to wait for.
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

  tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]

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


__all__ = [
  'amass',
]
