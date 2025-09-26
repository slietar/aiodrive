import asyncio
from asyncio import AbstractEventLoop, Future
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Condition, Lock


@dataclass(slots=True)
class ThreadsafeState[T]:
  """
  A thread-safe class for storing state that can be waited on.
  """

  value: T

  _condition: Condition = field(default_factory=(lambda: Condition(Lock())), init=False, repr=False)
  _futures: dict[AbstractEventLoop, Future[None]] = field(default_factory=dict, init=False, repr=False)

  def set_value(self, value: T, /):
    """
    Set the state value and wake up all registered waiters if it changed.

    Parameters
    ----------
    value
      The new state value.
    """

    with self._condition:
      if self.value != value:
        self.value = value

        self._condition.notify_all()

        # Using a copy because futures may be removed (but not added) while
        # iterating
        for future in self._futures.copy().values():
          try:
            future.get_loop().call_soon_threadsafe(future.set_result, None)
          except RuntimeError:
            pass

        self._futures.clear()

  def wait(self):
    """
    Block the current thread until the state changes.

    This method may not be called from a running event loop.

    Returns
    -------
    T
      The new state value, guaranteed to be different from the initial one.
    """

    if asyncio.get_running_loop() is not None:
      raise RuntimeError("Cannot call sync wait() from async context")

    old_value = self.value

    while self.value == old_value:
      with self._condition:
        self._condition.wait()

    return self.value

  def wait_until(self, fn: Callable[[T], bool], /):
    """
    Wait for a state change.

    Parameters
    ----------
    fn
      A function that takes the current state value and returns `True` if the
      wait should end.

    Returns
    -------
    T
      The new state value, guaranteed to be different from the initial one.
    """

    return self._observe(fn)

  async def _observe(self, fn: Callable[[T], bool], /):
    loop = asyncio.get_running_loop()

    # Using a loop in case the value was restored to its old value before being
    # awakened
    while True:
      with self._condition:
        if fn(self.value):
          return self.value

        future = self._futures.get(loop)

        if future is None:
          future = Future[None]()
          self._futures[loop] = future

      try:
        await asyncio.shield(future)
      finally:
        # This is atomic
        # self._futures.pop(loop, None)
        pass


__all__ = [
  'ThreadsafeState',
]
