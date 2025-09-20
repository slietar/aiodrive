import asyncio
from asyncio import Future

from .cancel import ensure_correct_cancellation


async def checkpoint():
  """
  Check that the current task was not cancelled.

  The current task may have been cancelled while performing a blocking
  operation, for example in the case of a KeyboardInterrupt.
  """

  ensure_correct_cancellation()

async def forced_checkpoint():
  """
  Wait for the next iteration of the event loop.
  """

  future = Future[None]()
  loop = asyncio.get_running_loop()
  loop.call_soon(future.set_result, None)

  await asyncio.shield(future)


__all__ = [
  'checkpoint',
  'forced_checkpoint',
]
