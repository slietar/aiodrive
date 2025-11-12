import asyncio
import contextlib
from asyncio import AbstractEventLoop


def get_event_loop():
  """
  Get the current event loop.

  Returns
  -------
  Optional[AbstractEventLoop]
    The current event loop, or `None` if there is none.
  """

  try:
    return asyncio.get_running_loop()
  except RuntimeError:
    return None


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
  'get_event_loop',
  'set_event_loop',
]
