import asyncio
import contextlib
import types
from asyncio import Task
from collections.abc import Awaitable


async def cancel_task(task: Task[object], /):
  """
  Cancel and await the provided task.

  Parameters
  ----------
  task
    The task to cancel.
  """

  if task.done():
    await task
  else:
    task.cancel()

    try:
      await task
    except asyncio.CancelledError:
      task.uncancel()

      if task.cancelling() > 1:
        raise


def prime[T](awaitable: Awaitable[T], /) -> Awaitable[T]:
  """
  Prime an awaitable such that as much code as possible is executed immediately.
  This is akin to creating tasks with `asyncio.eager_task_factory` as the task
  factory.

  It is safe to run this function on a different event loop or thread than the
  one where the returned coroutine is awaited.

  If the returned awaitable is not awaited, the closure of the original
  awaitable is only performed when the event loop is closed.

  Returns
  -------
  Awaitable[T]
    An awaitable that returns the result of the provided awaitable.
  """

  generator = awaitable.__await__()

  try:
    hint = generator.send(None)
  except StopIteration as e:
    hint = e.value
    returned = True
  else:
    returned = False

  @types.coroutine
  def inner():
    if returned:
      return hint

    yield hint
    result = yield from generator
    return result

  return inner()



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


async def cleanup_shield[T](awaitable: Awaitable[T], /) -> T:
  """
  Await the provided awaitable, shielding it if the current task has not been
  cancelled yet.

  If the call is cancelled while the awaitable is shielded, it is awaited again
  without shielding.

  Returns
  -------
  T
    The result of the awaitable.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  # TODO: Is there a difference with current_task.cancelled()?
  if current_task.cancelling() > 0:
    return await awaitable

  task = asyncio.ensure_future(awaitable)

  try:
    return await asyncio.shield(task)
  except asyncio.CancelledError:
    # If the task is not done, the call to asyncio.shield() was cancelled and
    # the task must be awaited again. Otherwise, the task raised a
    # CancelledError for some other reason and is thus finished.
    if not task.done():
      task.cancel()
      return await task

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
  'timeout',
]


if __name__ == '__main__':
  async def a(c):  # noqa: ANN001
    pass

  async def b():
    try:
      print("A")
      await asyncio.sleep(1)
      print("B")
      await asyncio.sleep(1)
      print("C")
      return 42
    finally:
      print("Close")

  async def main():
    # p = asyncio.sleep(1)
    # t = asyncio.create_task(prime(a(p)))
    # t.cancel()

    coro = prime(b())
    task = asyncio.ensure_future(coro)
    # await asyncio.sleep(1.5)
    task.cancel()

    # print(await coro)

    await asyncio.sleep(3)

    # print("Start")
    # value = await coro
    # print(value)

  asyncio.run(main())
