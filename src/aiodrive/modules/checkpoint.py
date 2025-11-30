import asyncio
from asyncio import Future


async def checkpoint():
  """
  Check that the current task was not cancelled.

  The current task may have been cancelled while performing a blocking
  operation, for example in the case of a KeyboardInterrupt.

  Raises
  ------
  asyncio.CancelledError
    If the current task was cancelled.
  """

  current_task = asyncio.current_task()
  assert current_task is not None

  if current_task.cancelling() > 0:
    raise asyncio.CancelledError


async def suspend():
  """
  Wait for the next iteration of the event loop.
  """

  future = Future[None]()
  loop = asyncio.get_running_loop()
  loop.call_soon(future.set_result, None)

  await asyncio.shield(future)


__all__ = [
  'checkpoint',
  'suspend',
]
