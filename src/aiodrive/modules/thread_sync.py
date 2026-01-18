import asyncio
import contextvars
from asyncio import Future
from collections.abc import Awaitable, Callable
from threading import Thread
from typing import Literal, Optional

from ..internal.future import ensure_future
from .cancel import suppress
from .event_loop import get_event_loop
from .future_state import FutureState
from .shield import shield_wait_forever
from .thread_safe_state import ThreadsafeState


def launch_in_thread_loop_sync[T](target: Awaitable[T], /):
  """
  Launch an awaitable in a separate thread with its own event loop.

  This function returns after the first iteration of the event loop in the
  thread has completed.

  Parameters
  ----------
  target
    The awaitable to run in a separate thread.

  Returns
  -------
  Awaitable[T]
    An awaitable which resolves to the result of the provided awaitable. The
    returned value must be awaited.
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

  context = contextvars.copy_context()

  thread = Thread(target=context.run, args=(thread_main,))
  thread.start()

  stage.wait_until_sync(lambda value: value == "running")

  def finish(cancel: bool):
    assert task is not None

    if cancel:
      try:
        task.get_loop().call_soon_threadsafe(task.cancel)
      except RuntimeError:
        pass

    stage.wait_until_sync(lambda value: value == "join")
    thread.join()

    assert result is not None

    with suppress(asyncio.CancelledError):
      return result.apply()

  return finish


def run_in_thread_loop_sync[T](target: Awaitable[T], /):
  """
  Run an awaitable in a separate thread with its own event loop.

  This function returns once the thread has terminated.

  Parameters
  ----------
  target
    The awaitable to run in a separate thread.

  Returns
  -------
  T
    The result of the provided awaitable.
  """

  return launch_in_thread_loop_sync(target)(cancel=False)


# Not public
def run_in_thread_loop_contextualized_sync[T](target: Awaitable[T], /):
  """
  Run an awaitable in a separate thread with its own event loop, using a
  context manager.

  The context manager's entry completes once the first iteration of the event
  loop of the thread has completed.

  Parameters
  ----------
  target
    The awaitable to run in a separate thread. Its return value is discarded.

  Returns
  -------
  AbstractAsyncContextManager[None]
    An async context manager which runs the provided awaitable in a separate
    thread.
  """

  finish = launch_in_thread_loop_sync(target)

  try:
    yield
  finally:
    finish(cancel=True)


def run_async[T](awaitable: Awaitable[T], /):
  """
  Synchronously run an awaitable.

  If there is already an event loop running in the current thread, the awaitable
  is run in a separate thread. Otherwise, it is run in the current thread.

  Parameters
  ----------
  awaitable
    The awaitable to run.

  Returns
  -------
  T
    The result of the awaitable.
  """

  # Avoid circular import
  from .thread_loop import run_in_thread_loop

  if get_event_loop() is not None:
    return run_in_thread_loop_sync(awaitable)
  else:
    return asyncio.run(run_in_thread_loop(awaitable))


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
  'launch_in_thread_loop_sync',
  'run_async',
  'run_in_thread_loop_sync',
  'to_thread',
]
