import asyncio
from typing import Awaitable


async def race(*awaitables: Awaitable):
  """
  Wait for the first awaitable to complete, and then cancel the others.

  The awaitables are wrapped as tasks which are awaited. The function returns or raises an exception according to the status of the first task that finishes. All awaitables are cancelled if the call to `race()` itself is cancelled.

  Parameters
    awaitables: The awaitables to wait for.

  Returns
    A tuple containing the index of the first completed awaitable and its result.

  Raises
    asyncio.CancelledError: If the call is cancelled.
  """

  tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]

  try:
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
  except asyncio.CancelledError:
    for task in tasks:
      task.cancel()

    await asyncio.wait(tasks)
    raise

  done_task = next(iter(done))

  for task in pending:
    task.cancel()

  if pending:
    await asyncio.wait(pending)

  return tasks.index(done_task), done_task.result()


__all__ = [
  'race'
]
