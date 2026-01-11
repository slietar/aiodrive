import asyncio
from asyncio import Future
from collections import deque
from dataclasses import dataclass, field
from threading import Condition as ThreadingCondition
from threading import Lock as ThreadingLock


@dataclass(slots=True)
class ThreadsafeLock:
  _locked: bool = field(default=False, init=False, repr=False)
  _waiters: deque[Future[None]] = field(default_factory=deque, init=False, repr=False)

  # _waiters_lock: ThreadingCondition = field(default_factory=ThreadingCondition, init=False, repr=False)
  _state_lock: ThreadingLock = field(default_factory=ThreadingLock, init=False, repr=False)
  _sync_lock: ThreadingLock = field(default_factory=ThreadingLock, init=False, repr=False)


  def __enter__(self):
    self.acquire_sync()

  def __exit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    self.release_sync()

  def acquire_sync(self):
    while True:
      self._sync_lock.acquire()

      with self._state_lock:
        if not self._locked:
          self._locked = True
          break

        self._sync_lock.release()

  def release_sync(self):
    self.release_async()


  async def __aenter__(self):
    await self.acquire_async()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    self.release_async()

  async def acquire_async(self):
    with self._state_lock:
      if not self._locked:
        self._sync_lock.acquire()
        self._locked = True
        return

      future = Future[None]()
      self._waiters.append(future)

    # We purposefully let the future potentially be cancelled
    await future

  def release_async(self):
    with self._state_lock:
      while self._waiters:
        future = self._waiters.popleft()

        if future.cancelled():
          continue

        try:
          future.get_loop().call_soon_threadsafe(future.set_result, None)
        except RuntimeError:
          continue

        break
      else:
        self._locked = False
        self._sync_lock.release()


@dataclass(slots=True)
class ThreadsafeCondition:
  lock: ThreadsafeLock = field(default_factory=ThreadsafeLock, init=False, repr=False)
  _waiters: set[Future[None]] = field(default_factory=set, init=False, repr=False)

  def notify(self):
    for waiter in list(self._waiters):
      if not waiter.cancelled():
        try:
          waiter.get_loop().call_soon_threadsafe(waiter.set_result, None)
        except RuntimeError:
          pass

    self._waiters.clear()

  async def wait(self):
    self.lock.release_async()

    future = Future[None]()
    self._waiters.add(future)

    try:
      await future
    finally:
      await self.lock.acquire_async()

  async def __aenter__(self):
    await self.lock.acquire_async()

  async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
    self.lock.release_async()


__all__ = [
  'ThreadsafeCondition',
  'ThreadsafeLock',
]
