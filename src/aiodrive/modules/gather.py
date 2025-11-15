import asyncio
from collections.abc import Awaitable, Iterable
from typing import overload


@overload
async def gather[T1](*, sensitive: bool = ...) -> tuple[()]:
  ...

@overload
async def gather[T1](
  awaitable1: Awaitable[T1],
  /, *,
  sensitive: bool = ...,
) -> tuple[T1, ...]:
  ...

@overload
async def gather[T1, T2](
  awaitable1: Awaitable[T1],
  awaitable2: Awaitable[T2],
  /, *,
  sensitive: bool = ...,
) -> tuple[T1, T2]:
  ...

@overload
async def gather[T1, T2, T3](
  awaitable1: Awaitable[T1],
  awaitable2: Awaitable[T2],
  awaitable3: Awaitable[T3],
  /, *,
  sensitive: bool = ...,
) -> tuple[T1, T2, T3]:
  ...

@overload
async def gather[T](*awaitables: Awaitable[T], sensitive: bool = ...) -> tuple[T, ...]:
  ...

@overload
async def gather[T](awaitables: Iterable[Awaitable[T]], /, *, sensitive: bool = ...) -> tuple[T, ...]:
  ...


async def gather(*awaitables: Awaitable | Iterable[Awaitable], sensitive: bool = True):
  """
  Concurrently collect results from multiple awaitables.

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
    Whether to cancel other tasks as soon as a task raises an exception.

  Returns
  -------
  tuple[T, ...]
    Results from the provided tasks, in the same order as the awaitables.

  Raises
  ------
  BaseExceptionGroup
    If an awaitable raises an exception.
  """

  if awaitables and not isinstance(awaitables[0], Awaitable):
    assert len(awaitables) == 1
    effective_awaitables = awaitables[0]
  else:
    effective_awaitables: Iterable[Awaitable] = awaitables # type: ignore

  cancelled = False
  tasks = [asyncio.ensure_future(awaitable) for awaitable in effective_awaitables]

  if not tasks:
    return ()

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

  # This can potentially be added later on
  #
  # for e in exceptions:
  #   if isinstance(e, KeyboardInterrupt | SystemExit):
  #     raise e

  if exceptions:
    raise BaseExceptionGroup("", exceptions)

  # Still raise an asyncio.CancelledError if any task was externally cancelled
  # The check on "canceled" is not redundant as tasks may have suppressed their
  # cancellation
  if cancelled or any(task.cancelled() for task in tasks):
    raise asyncio.CancelledError

  return tuple(task.result() for task in tasks)


__all__ = [
  'gather',
]
