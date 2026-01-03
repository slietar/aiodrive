import asyncio
from collections.abc import Awaitable
from threading import Thread
from typing import Literal, Optional

from .cancel import suppress
from .future_state import FutureState
from .thread_safe_state import ThreadsafeState


def run_in_thread_loop_contextualized_sync[T](target: Awaitable[T], /):
  result: Optional[FutureState[T]] = None
  stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
  task: Optional[asyncio.Task[T]] = None

  def thread_main():
    nonlocal result, stage

    result = FutureState.absorb_lambda(asyncio.run, thread_main_async())
    stage.set_value("join")

  async def thread_main_async():
    nonlocal task

    loop = asyncio.get_running_loop()

    task = asyncio.ensure_future(target)
    loop.call_soon(stage.set_value, "running")

    return await task

  thread = Thread(target=thread_main)
  thread.start()

  try:
    stage.wait_until_sync(lambda value: value == "running")
    yield
  finally:
    assert task is not None

    try:
      task.get_loop().call_soon_threadsafe(task.cancel)
    except RuntimeError:
      pass

    stage.wait_until_sync(lambda value: value == "join")
    thread.join()

  with suppress(asyncio.CancelledError):
    result.apply()
