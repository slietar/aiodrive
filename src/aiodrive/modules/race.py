import asyncio
from collections.abc import Awaitable
from typing import Literal, overload


@overload
async def race[T1](a1: Awaitable[T1], /) -> tuple[Literal[0], T1]:
  ...

@overload
async def race[T1, T2](a1: Awaitable[T1], a2: Awaitable[T2], /) -> tuple[Literal[0], T1] | tuple[Literal[1], T2]:
  ...

@overload
async def race[T1, T2, T3](a1: Awaitable[T1], a2: Awaitable[T2], a3: Awaitable[T3], /) -> tuple[Literal[0], T1] | tuple[Literal[1], T2] | tuple[Literal[2], T3]:
  ...

@overload
async def race[T](*awaitables: Awaitable[T]) -> tuple[int, T]:
  ...

async def race(*awaitables: Awaitable):
  """
  Wait for the first awaitable to complete, and then cancel the others.

  The function returns or raises an exception according to the status of the
  first task that finishes. All awaitables are cancelled if the call to `race()`
  itself is cancelled.

  Parameters
  ----------
  awaitables
    The awaitables to wait for.

  Returns
  -------
  tuple[int, Any]
    A tuple containing the index of the first completed awaitable and its
    result.
  """

  assert len(awaitables) >= 1

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
  'race',
]
