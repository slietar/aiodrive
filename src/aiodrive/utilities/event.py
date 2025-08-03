import asyncio
import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class ThreadSafeEvent:
  _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
  _set: bool = field(default=False, init=False)
  _waiters: deque[asyncio.Future] = field(default_factory=deque, init=False)

  def _wakeup_waiter(self, waiter: asyncio.Future):
    if not waiter.done():
      waiter.set_result(None)

  def clear(self):
    with self._lock:
      self._set = False

  def set(self):
    with self._lock:
      if not self._set:
        self._set = True

        for waiter in self._waiters:
          waiter.get_loop().call_soon_threadsafe(self._wakeup_waiter, waiter)

        self._waiters.clear()

  async def wait(self):
    if not self._set:
      future = asyncio.Future()
      self._waiters.append(future)

      try:
        await future
      except:
        with self._lock:
          if future in self._waiters:
            self._waiters.remove(future)

        raise
