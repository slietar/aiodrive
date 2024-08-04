import asyncio
from asyncio import Task
from typing import Any, Coroutine, Iterable, Optional


async def try_all(items: Iterable[Coroutine[Any, Any, Any] | Task[Any]], /):
  """
  Wait for all provided coroutines or tasks to complete, cancelling other tasks if one of them raises an exception.

  All coroutines passed as argument are converted to tasks. If an exception is raised by one of the tasks, the other tasks are cancelled and awaited. The remaining behavior is similar to that of `wait_all()`.

  Raises
    asyncio.CancelledError: If the call is cancelled.
  """

  if not items:
    return

  cancelled_exc: Optional[asyncio.CancelledError] = None
  tasks = [item if isinstance(item, Task) else asyncio.create_task(item) for item in items]

  try:
    await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
  except asyncio.CancelledError as e:
    cancelled_exc = e

    for task in tasks:
      task.cancel()

  await wait_all(tasks)

  if cancelled_exc:
    raise cancelled_exc


async def wait_all(items: Iterable[Coroutine[Any, Any, Any] | Task[Any]], /):
  """
  Wait for all provided coroutines or tasks to complete.

  All coroutines passed as argument are converted to tasks. If an exception is raised by one of the tasks, the other tasks are still awaited without being cancelled, until all tasks finish. If a single exception has been raised while awaiting tasks, it is re-raised. If more than one exception has been raised, a `BaseExceptionGroup` is raised with the caught exceptions.

  If the call to `wait_all()` is cancelled, all unfinished tasks are cancelled and awaited. The `asyncio.CancelledError` exception is re-raised if no exception was raised by the tasks, otherwise the procedure described earlier is applied. If another cancellation occurs while still awaiting the tasks, tasks are cancelled and awaited again.

  Parameters
    items: The coroutines or tasks to wait for. The function returns immediately if the iterable is empty.

  Raises
    asyncio.CancelledError: If the call is cancelled.
  """

  if not items:
    return

  cancelled_exc: Optional[asyncio.CancelledError] = None
  tasks = [item if isinstance(item, Task) else asyncio.create_task(item) for item in items]

  while True:
    try:
      await asyncio.wait(tasks)
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


__all__ = [
  'try_all',
  'wait_all'
]
