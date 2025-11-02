import asyncio
import contextlib
from asyncio import AbstractEventLoop


@contextlib.contextmanager
def set_event_loop(loop: AbstractEventLoop, /):
  """
  Set the current event loop.

  Parameters
  ----------
  loop
    The loop which should be set as the current event loop.

  Returns
  -------
  AbstractContextManager[None]
    A context manager which sets the event loop when entered and restores the
    previous event loop when exited.
  """

  old_loop = asyncio._get_running_loop()

  try:
    asyncio._set_running_loop(loop)
    yield
  finally:
    asyncio._set_running_loop(old_loop)


__all__ = [
  'set_event_loop',
]
