import asyncio
from asyncio import Future
from collections.abc import Awaitable, Callable
from threading import Thread
from typing import Literal, Optional

from ..internal.future import ensure_future
from .cancel import suppress
from .future_state import FutureState
from .shield import shield_wait_forever
from .thread_safe_state import ThreadsafeState


def run_in_thread_loop_contextualized_sync[T](target: Awaitable[T], /):
  """
  Run an awaitable in a separate thread with its own event loop.

  Parameters
  ----------
  target
      The awaitable to run in a separate thread.

  Returns
  -------
  T
      The result of the provided awaitable.
  """

  result: Optional[FutureState[T]] = None
  stage = ThreadsafeState[Literal["join", "preparing", "running"]]("preparing")
  task: Optional[Future[T]] = None

  def thread_main():
    nonlocal result, stage

    result = FutureState.absorb_lambda(asyncio.run, thread_main_async())
    stage.set_value("join")

  async def thread_main_async():
    nonlocal task

    loop = asyncio.get_running_loop()

    task = ensure_future(target)
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


async def to_thread[**P, T](func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
  """
  Run a function in a separate thread.

  This function is similar to `asyncio.to_thread()` but indefinitely shields the
  operation against cancellation.

  Parameters
  ----------
  func
    The function to run.
  *args
    positional arguments to pass to the function.
  **kwargs
    Keyword arguments to pass to the function.

  Returns
  -------
  T
    The result of the function.
  """

  return await shield_wait_forever(asyncio.to_thread(func, *args, **kwargs))


__all__ = [
  'run_in_thread_loop_contextualized_sync',
  'to_thread',
]
