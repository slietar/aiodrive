import asyncio
from collections.abc import Awaitable


def arun[T](awaitable: Awaitable[T], /):
  """
  Run an awaitable in a new event loop while enforcing structured concurrency.

  Unlike `asyncio.run`, there must not be any extraneous task or async generator
  left after the awaitable finishes.

  Parameters
  ----------
  awaitable
    An awaitable to run.

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

  loop = asyncio.new_event_loop()

  try:
    return loop.run_until_complete(awaitable)
  finally:
    loop.run_until_complete(loop.shutdown_default_executor())

    if isinstance(loop, asyncio.BaseEventLoop):
      if loop._asyncgens: # type: ignore
        raise RuntimeError("Unclosed async generators at event loop shutdown")

    if asyncio.all_tasks(loop):
      raise RuntimeError("Unfinished tasks at event loop shutdown")

    loop.close()
