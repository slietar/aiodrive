from asyncio import Task
import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any, Awaitable, Coroutine, TypeVar


async def cancel_task(task: Task[Any], /):
  """
  Silently cancel and then await the provided task, if any.

  The task is cancelled and then awaited. The `asyncio.CancelledError` instance raised by the task is ignored.

  Parameters
    task: The task to cancel, or `None`.
  """

  task.cancel()

  try:
    await task
  except asyncio.CancelledError:
    task.uncancel()


@dataclass(slots=True)
class AwaitableHint:
  hint: Any

  def __await__(self):
    yield self.hint

async def primed(coro: Coroutine, start_hint: Any):
  hint = start_hint

  while True:
    await AwaitableHint(hint)

    try:
      hint = await coro.send(None)
    except StopIteration as e:
      return e.value

def prime[T](coro: Coroutine[Any, Any, T], /) -> Awaitable[T]:
  hint = coro.send(None)
  return primed(coro, hint)


async def shield[T](awaitable: Awaitable[T], /) -> T:
  """
  Shield and then await the provided awaitable from cancellation.

  The provided awaitable is wrapped in a task and then awaited with `asyncio.shield()`. If the call to `shield()` is cancelled, the task is awaited again and the exception is then re-raised. If the call is cancelled again, the task is cancelled without shielding.

  Returns
    The task's result, assuming no cancellation occurs.

  Raises
    asyncio.CancelledError: If the call to `shield()` is cancelled and after the task finishes.
  """

  task = asyncio.ensure_future(awaitable)

  try:
    return await asyncio.shield(task)
  except asyncio.CancelledError:
    await task
    raise


@contextlib.asynccontextmanager
async def timeout(seconds: float, /):
  """
  A context manager that raises a `TimeoutError` if the block takes longer than the provided time.

  Parameters
    seconds: The time in seconds before raising a `TimeoutError`.

  Raises
    TimeoutError: If the block takes longer than the provided time.
  """

  current_task = asyncio.current_task()
  assert current_task

  async def timeout_coro():
    await asyncio.sleep(seconds)
    current_task.cancel()

  cancelled = False
  timeout_task = asyncio.create_task(timeout_coro())

  try:
    yield
  except asyncio.CancelledError:
    cancelled = True
  finally:
    if not timeout_task.done():
      timeout_task.cancel()

    try:
      await timeout_task
    except asyncio.CancelledError:
      current_task.uncancel()
      raise TimeoutError from None

    if cancelled:
      raise asyncio.CancelledError


__all__ = [
  'cancel_task',
  'prime',
  'shield',
  'timeout'
]
