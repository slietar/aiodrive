import asyncio
from collections.abc import Awaitable, Iterable

from ..modules.wait import wait


async def amass[T](awaitables: Iterable[Awaitable[T]], /, *, sensitive: bool = True):
  """
  Asynchronously yield results from awaitables as they complete.

  Parameters
  ----------
  awaitables
    The awaitables to wait for.
  sensitive
    Whether to stop yielding results as soon as an exception is raised by one of
    the awaitables. If `True` and if a successful and a failed awaitable both
    finish during the same iteration of the event loop, it is unspecified
    whether the result is yielded before the exception is raised.

  Yields
  ------
  T
    Results from the provided awaitables as they complete.

  Raises
  ------
  BaseExceptionGroup
    If at least one awaitable raises an exception.
  """

  tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]

  if not tasks:
    return

  pending_tasks = set(tasks)
  running = True

  while running:
    try:
      done_tasks, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
      for task in pending_tasks:
        task.cancel()

      await wait(tasks, sensitive=False)
      raise

    for task in done_tasks:
      try:
        result = task.result()
      except:  # noqa: E722
        if sensitive:
          running = False
          break
      else:
        try:
          yield result
        except GeneratorExit:
          await wait(tasks, sensitive=False)
          raise

    if not pending_tasks:
      break

  await wait(tasks, sensitive=False)


__all__ = [
  'amass',
]


async def main():
  async def gen(delay: float, value: int):
    await asyncio.sleep(delay)
    return value

  async def fail(delay: float):
    await asyncio.sleep(delay)
    raise ValueError("Intentional failure")

  async for result in amass([
    gen(1.5, 3),
    gen(.5, 1),
    gen(1, 2),
    fail(0.75),
    fail(0.75),
  ], sensitive=True):
    print("Got result:", result)

  # current_task = asyncio.current_task()
  # assert current_task is not None

  # current_task.cancel()
  # print(current_task.cancelling())
  # current_task.cancel()
  # print(current_task.cancelling())

  # try:
  #   await asyncio.sleep(1)
  # except asyncio.CancelledError:
  #   print(current_task.cancelling())

  # try:
  #   await asyncio.sleep(1)
  # except asyncio.CancelledError:
  #   print(current_task.cancelling())
  # else:
  #   print("Not cancelled")

  # async def a():
  #   raise asyncio.CancelledError

  # try:
  #   # await asyncio.sleep(1)
  #   await a()
  # except asyncio.CancelledError:
  #   pass

  # asyncio.current_task().uncancel()
  # await asyncio.sleep(1)


asyncio.run(main())
