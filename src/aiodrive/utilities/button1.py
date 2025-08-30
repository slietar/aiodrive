import asyncio
from asyncio import AbstractEventLoop, Future
from dataclasses import dataclass, field
from threading import Condition, Lock


@dataclass(slots=True)
class ThreadSafeButton:
  _condition: Condition = field(default_factory=(lambda: Condition(Lock())), init=False, repr=False)
  _futures: dict[AbstractEventLoop, Future[None]] = field(default_factory=dict, init=False, repr=False)

  def press(self):
    with self._condition:
      self._condition.notify_all()

      for future in self._futures.values():
        future.get_loop().call_soon_threadsafe(future.set_result, None)

      self._futures.clear()

  def wait(self):
    if asyncio.get_running_loop() is not None:
      raise RuntimeError("Cannot call sync wait() from async context")

    with self._condition:
      self._condition.wait()

  def __await__(self):
    with self._condition:
      loop = asyncio.get_running_loop()

      future = self._futures.get(loop)

      if future is None:
        future = Future()
        self._futures[loop] = future

      return asyncio.shield(future).__await__()
