import asyncio
import asyncio.runners
from asyncio import AbstractEventLoop, BaseEventLoop
from collections.abc import Awaitable
from typing import Optional


def run[T](awaitable: Awaitable[T], /, *, loop: Optional[AbstractEventLoop] = None):
  """
  Run an awaitable in an event loop with enforced structured concurrency.

  Unlike `asyncio.run`, there must not be any extraneous task or async generator
  left after the awaitable finishes.

  Parameters
  ----------
  awaitable
    The awaitable to run.
  loop
    The event loop to use. It is closed before returning. Defaults to a new
    event loop.

  Returns
  -------
  T
    The result of the awaitable.

  Raises
  ------
  RuntimeError
    If there are unclosed async generators or unfinished tasks at event loop
    shutdown.
  """

  if loop is not None:
    assert not loop.is_closed()
    assert not loop.is_running()

    effective_loop = loop
  else:
    effective_loop = asyncio.new_event_loop()

  try:
    try:
      return effective_loop.run_until_complete(awaitable)
    finally:
      effective_loop.run_until_complete(effective_loop.shutdown_default_executor())

      if isinstance(effective_loop, BaseEventLoop) and effective_loop._asyncgens: # type: ignore
          # This does not raise but prints exceptions that occur during shutdown
          effective_loop.run_until_complete(effective_loop.shutdown_asyncgens())
          asyncio.runners._cancel_all_tasks(effective_loop) # type: ignore

          # raise RuntimeError('Unclosed async generators at event loop shutdown')

      if asyncio.all_tasks(effective_loop):
        # Same here
        asyncio.runners._cancel_all_tasks(effective_loop) # type: ignore

        # raise RuntimeError('Unfinished tasks at event loop shutdown')

  finally:
    effective_loop.close()


__all__ = [
  'run',
]
