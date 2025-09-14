import asyncio
from asyncio import AbstractEventLoop, Future
from dataclasses import dataclass, field
from threading import Condition, Lock


@dataclass(slots=True)
class ThreadsafeButton:
  """
  A thread-safe class that wakes up registered waiters when called.
  """

  _condition: Condition = field(default_factory=(lambda: Condition(Lock())), init=False, repr=False)
  _futures: dict[AbstractEventLoop, Future[None]] = field(default_factory=dict, init=False, repr=False)

  def press(self):
    """
    Wake up all registered waiters.
    """

    with self._condition:
      self._condition.notify_all()

      for future in self._futures.values():
        try:
          future.get_loop().call_soon_threadsafe(future.set_result, None)
        except RuntimeError:
          pass

      self._futures.clear()

  def wait(self):
    """
    Block the current thread until the button is pressed.

    This method may not be called from a running event loop.
    """

    if asyncio.get_running_loop() is not None:
      raise RuntimeError("Cannot call sync wait() from async context")

    with self._condition:
      self._condition.wait()

  def __await__(self):
    """
    Wait until the button is pressed.
    """

    with self._condition:
      loop = asyncio.get_running_loop()
      future = self._futures.get(loop)

      if future is None:
        future = Future[None]()
        self._futures[loop] = future

      return asyncio.shield(future).__await__()


__all__ = [
  'ThreadsafeButton',
]
