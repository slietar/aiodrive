import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Awaitable
from typing import Optional


def arun[T](awaitable: Awaitable[T], /, *, loop: Optional[AbstractEventLoop]):
  """
  Run an awaitable in an event loop while enforcing structured concurrency.

  Unlike `asyncio.run`, there must not be any extraneous task or async generator
  left after the awaitable finishes.

  Parameters
  ----------
  awaitable
    The awaitable to run.
  loop
    The event loop to use. Defaults to a new event loop.

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

  effective_loop = loop if loop is not None else asyncio.new_event_loop()

  try:
    return effective_loop.run_until_complete(awaitable)
  finally:
    effective_loop.run_until_complete(effective_loop.shutdown_default_executor())

    if isinstance(effective_loop, asyncio.BaseEventLoop):
      if effective_loop._asyncgens: # type: ignore
        raise RuntimeError('Unclosed async generators at event loop shutdown')

    if asyncio.all_tasks(effective_loop):
      raise RuntimeError('Unfinished tasks at event loop shutdown')

    effective_loop.close()


__all__ = [
  'arun',
]
