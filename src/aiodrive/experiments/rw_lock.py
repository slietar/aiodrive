import asyncio
import contextlib
from asyncio import Future
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Literal, NewType


Id = NewType("Id", int)


@dataclass(slots=True)
class ThreadsafeRWLock:
  _next_id: int = field(default=0, init=False)
  _queue_read: list[tuple[Id, Future[None]]] = field(default_factory=list, init=False)
  _queue_write: deque[tuple[Id, Future[None]]] = field(default_factory=deque, init=False)
  _state: Literal["unlocked", "read", "write"] = field(default="unlocked", init=False)
  _state_lock: Lock = field(default_factory=Lock, init=False)
  _state_owner_ids: set[int] = field(default_factory=set, init=False)

  @contextlib.asynccontextmanager
  async def _acquire(self, target: Literal["read", "write"]):
    with self._state_lock:
      current_id = Id(self._next_id)
      self._next_id += 1

      match (self._state, target):
        case ("unlocked", _) | ("read", "read"):
          future = None
          self._state = target
          self._state_owner_ids.add(current_id)
        case ("write", "read"):
          future = Future[None]()
          self._queue_read.append((current_id, future))
        case (_, "write"):
          future = Future[None]()
          self._queue_write.append((current_id, future))

    def release():
      with self._state_lock:
        if current_id in self._state_owner_ids:
          # If the current task was cancelled while waiting for the future, then
          # then id is not in the set. If it was cancelled during the yield, it
          # is in the set.
          self._state_owner_ids.discard(current_id)

        if not self._state_owner_ids:
          if self._queue_write:
            next_id, next_future = self._queue_write.popleft()
            next_future.get_loop().call_soon_threadsafe(next_future.set_result, None)

            self._state = "write"
            self._state_owner_ids.add(next_id)
          elif self._queue_read:
            self._state = "read"

            for next_id, next_future in self._queue_read:
              next_future.get_loop().call_soon_threadsafe(next_future.set_result, None)
              self._state_owner_ids.add(next_id)

            self._queue_read.clear()
          else:
            self._state = "unlocked"

    if future is not None:
      try:
        # Shielding such that another thread may still set the result of the future.
        await asyncio.shield(future)
      except asyncio.CancelledError:
        release()
        raise

    try:
      yield
    finally:
      release()

  def acquire_read(self):
    return self._acquire("read")

  def acquire_write(self):
    return self._acquire("write")


__all__ = [
  'ThreadsafeRWLock',
]


# async def main():
#   lock = ThreadSafeRWLock()

#   async def a():
#     async with lock.acquire_read():
#       print("Acquired read lock")
#       async with lock.acquire_read():
#         print("Acquired nested read lock")
#         await asyncio.sleep(1)
#         print("Releasing nested read lock")
#       await asyncio.sleep(1)
#       print("Releasing read lock")

#   async def b():
#     async with lock.acquire_write():
#       print("Acquired write lock")

#   async def c():
#     async with lock.acquire_read():
#       print("Acquired read lock 2")

#   async with TaskGroup() as group:
#     group.create_task(a())
#     group.create_task(b())
#     group.create_task(c())

# asyncio.run(main())
