import asyncio
import contextlib
from asyncio import Task

from aiodrive.modules.prime import prime


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
  ,
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
