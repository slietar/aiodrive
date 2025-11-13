import asyncio
from collections.abc import Awaitable, Iterable, Sequence


# TODO: Rename wait_concurrently

async def wait_all[T](awaitables: Iterable[Awaitable[T]], /, *, sensitive: bool = True) -> Sequence[T]:
  """
  Wait for all provided coroutines or tasks to complete.

  If an exception is raised by one of the tasks, the other tasks are still
  awaited without being cancelled, until all tasks finish. If a single exception
  is raised while awaiting tasks, it is re-raised. If more than one exception is
  raised, a `BaseExceptionGroup` is raised with the caught exceptions.

  If the call to this function is cancelled, all unfinished tasks are cancelled
  and awaited. The `asyncio.CancelledError` exception is re-raised if no other
  exception was raised by the tasks, otherwise the procedure described earlier
  is applied. If another cancellation occurs while still awaiting the tasks,
  tasks are cancelled and awaited again.

  Parameters
  ----------
  awaitables
    The awaitables or tasks to wait for. The function returns immediately if the
    iterable is empty.
  sensitive
    Whether to cancel other tasks as soon as one task raises an exception.

  Returns
  -------
  Sequence[T]
    A sequence of results from the provided tasks, in the same order as the
    provided items.

  Raises
  ------
  BaseExceptionGroup
    If one or more exceptions were raised by the provided tasks.
  """

  cancelled = False
  tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]

  if not tasks:
    return []

  if sensitive:
    try:
      done_tasks, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    except asyncio.CancelledError:
      cancelled = True
      failed = False

      for task in tasks:
        task.cancel()
    else:
      failed = any(task.cancelled() or (task.exception() is not None) for task in done_tasks)

      if failed:
        for task in tasks:
          task.cancel()
  else:
    failed = False

  while True:
    try:
      await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    except asyncio.CancelledError:
      cancelled = True

      # If tasks were already cancelled due to an exception, don't cancel them
      # again the first time
      if failed:
        failed = False
      else:
        for task in tasks:
          task.cancel()
    else:
      break

  exceptions = [exc for task in tasks if not task.cancelled() and (exc := task.exception()) is not None]

  if exceptions:
    raise BaseExceptionGroup("", exceptions)

  # Still raise an asyncio.CancelledError if any task was externally cancelled
  # The check on "canceled" is not redundant as tasks may have suppressed their
  # cancellation
  if cancelled or any(task.cancelled() for task in tasks):
    raise asyncio.CancelledError

  return [task.result() for task in tasks]


__all__ = [
  'wait_all',
]


if __name__ == "__main__":
  import asyncio

  async def a():
    await asyncio.sleep(1)
    print("A done")
    raise Exception("Test exception")

  async def main():
    await wait_all([
      a(),
      asyncio.sleep(2),
    ], sensitive=False)

    # async with asyncio.TaskGroup() as tg:
    #   tg.create_task(a())
    #   tg.create_task(asyncio.sleep(2))

  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("Cancelled by user")
    raise
