import asyncio
from asyncio import Future
from collections import deque
from dataclasses import dataclass, field
from threading import Lock as ThreadingLock


@dataclass(slots=True)
class ThreadsafeLock:
  _futures: deque[Future[None]] = field(default_factory=deque, init=False, repr=False)
  _locked: bool = field(default=False, init=False, repr=False)
  _sync_lock: ThreadingLock = field(default_factory=ThreadingLock, init=False, repr=False)

  def __enter__(self):
    asyncio.run(self.__aenter__())

  def __exit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    asyncio.run(self.__aexit__(exc_type, exc_value, traceback))

  async def __aenter__(self):
    with self._sync_lock:
      if not self._locked:
        self._locked = True
        return

      future = Future[None]()
      self._futures.append(future)

    # We purposefully let the future potentially be cancelled
    await future

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    with self._sync_lock:
      while self._futures:
        future = self._futures.popleft()

        if future.cancelled():
          continue

        try:
          future.get_loop().call_soon_threadsafe(future.set_result, None)
        except RuntimeError:
          continue

        break
      else:
        self._locked = False


__all__ = [
  'ThreadsafeLock',
]
