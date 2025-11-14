import asyncio
from collections.abc import Awaitable, Iterable
from typing import Literal, overload

from .wait import wait


@overload
async def race[T1](
  awaitable1: Awaitable[T1],
  /,
) -> tuple[Literal[0], T1]:
  ...

@overload
async def race[T1, T2](
  awaitable1: Awaitable[T1],
  awaitable2: Awaitable[T2],
  /,
) -> tuple[Literal[0], T1] | tuple[Literal[1], T2]:
  ...

@overload
async def race[T1, T2, T3](
  awaitable1: Awaitable[T1],
  awaitable2: Awaitable[T2],
  awaitable3: Awaitable[T3],
  /,
) -> tuple[Literal[0], T1] | tuple[Literal[1], T2] | tuple[Literal[2], T3]:
  ...

@overload
async def race[T](*awaitables: Awaitable[T]) -> tuple[int, T]:
  ...

@overload
async def race[T](awaitables: Iterable[Awaitable[T]], /) -> tuple[int, T]:
  ...

async def race(*awaitables: Awaitable | Iterable[Awaitable]):
  """
  Wait for the first awaitable to complete, and then cancel the others.

  The function returns or raises an exception according to the status of the
  first task that finishes. All awaitables are cancelled if the call to itself
  is cancelled.

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

  if awaitables and isinstance(awaitables[0], Iterable):
    assert len(awaitables) == 1
    effective_awaitables = tuple(awaitables[0])
  else:
    effective_awaitables: tuple[Awaitable, ...] = awaitables # type: ignore

  assert len(effective_awaitables) >= 1
  tasks = [asyncio.ensure_future(awaitable) for awaitable in effective_awaitables]

  try:
    done_tasks, pending_tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
  except asyncio.CancelledError:
    for task in tasks:
      task.cancel()

    await wait(tasks)
    raise

  winning_task = next(iter(done_tasks))

  for task in pending_tasks:
    task.cancel()

  await wait(pending_tasks)
  return tasks.index(winning_task), winning_task.result()


__all__ = [
  'race',
]
