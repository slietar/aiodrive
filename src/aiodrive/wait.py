import asyncio
from asyncio import Task
from collections.abc import Awaitable, Sequence
from typing import Optional
from collections.abc import Iterable


async def try_all[T](items: Iterable[Awaitable[T]], /) -> Sequence[T]:
  """
  Wait for all provided coroutines or tasks to complete, cancelling other tasks
  if one of them raises an exception.

  All coroutines passed as argument are converted to tasks. If an exception is
  raised by one of the tasks, the other tasks are cancelled and awaited. The
  remaining behavior is similar to that of `wait_all()`.

  Parameters
  ----------
  items
    The coroutines or tasks to wait for. The function returns immediately if the
    iterable is empty.
  """

  cancelled_exc: Optional[asyncio.CancelledError] = None
  tasks = [item if isinstance(item, Task) else asyncio.create_task(item) for item in items] # type: ignore

  if not tasks:
    return []

  try:
    await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
  except asyncio.CancelledError as e:
    cancelled_exc = e

    for task in tasks:
      task.cancel()

  try:
    return await wait_all(tasks)
  finally:
    if cancelled_exc:
      raise cancelled_exc


async def wait_all[T](items: Iterable[Awaitable[T]], /) -> Sequence[T]:
  """
  Wait for all provided coroutines or tasks to complete.

  All coroutines passed as argument are converted to tasks. If an exception is
  raised by one of the tasks, the other tasks are still awaited without being
  cancelled, until all tasks finish. If a single exception is raised while
  awaiting tasks, it is re-raised. If more than one exception is raised, a
  `BaseExceptionGroup` is raised with the caught exceptions.

  If the call to this function is cancelled, all unfinished tasks are cancelled
  and awaited. The `asyncio.CancelledError` exception is re-raised if no other
  exception was raised by the tasks, otherwise the procedure described earlier
  is applied. If another cancellation occurs while still awaiting the tasks,
  tasks are cancelled and awaited again.

  Parameters
  ----------
  items
    The coroutines or tasks to wait for. The function returns immediately if the
    iterable is empty.
  """

  cancelled_exc: Optional[asyncio.CancelledError] = None
  tasks = [item if isinstance(item, Task) else asyncio.create_task(item) for item in items] # type: ignore

  if not tasks:
    return []

  while True:
    try:
      await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    except asyncio.CancelledError as e:
      cancelled_exc = e

      for task in tasks:
        task.cancel()
    else:
      break

  exceptions = [exc for task in tasks if (exc := task.exception())]

  if len(exceptions) >= 2:
    raise BaseExceptionGroup("ExceptionGroup", exceptions)
  elif exceptions:
    raise exceptions[0]

  if cancelled_exc:
    raise cancelled_exc

  return [task.result() for task in tasks if not task.cancelled()]


__all__ = [
  'try_all',
  'wait_all',
]
