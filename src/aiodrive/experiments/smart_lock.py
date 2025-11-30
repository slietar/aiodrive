import asyncio
import contextlib
import threading
from asyncio import Future
from dataclasses import dataclass, field
from threading import Lock as ThreadingLock
from threading import Thread
from typing import Literal, Optional

from ..modules.scope import Scope, use_scope


type SmartLockMode = Literal['exclusive', 'shared']
type SmartLockScope = Literal['global', 'task', 'thread', 'context']

@dataclass(slots=True)
class SmartLockWaiter:
  mode: SmartLockMode
  scope: SmartLockScope
  weak: bool

  future: Future[None]
  thread: Thread


@dataclass(slots=True)
class SmartLockOwner:
  context_scope: Optional[Scope]
  waiter: SmartLockWaiter


@dataclass(slots=True)
class SmartLock:
  _next_waiter_id: int = field(default=0, init=False, repr=False)
  _sync_lock: ThreadingLock = field(default_factory=ThreadingLock, init=False, repr=False)
  _owners: dict[int, SmartLockOwner] = field(default_factory=dict, init=False, repr=False)
  _waiters: dict[int, SmartLockWaiter] = field(default_factory=dict, init=False, repr=False)

  @contextlib.asynccontextmanager
  async def use(
    self,
    mode: SmartLockMode,
    scope: SmartLockScope,
    weak: bool = False,
  ):
    with self._sync_lock:
      # Also used to handle priority
      waiter_id = self._next_waiter_id
      self._next_waiter_id += 1

      waiter = SmartLockWaiter(
        mode=mode,
        scope=scope,
        weak=weak,

        future=Future[None](),
        thread=threading.current_thread(),
      )

      self._waiters[waiter_id] = waiter
      self._update()

      # TODO: Also target weak owners

    try:
      await asyncio.shield(waiter.future)

      with use_scope() as context_scope:
        self._owners[waiter_id].context_scope = context_scope
        yield
    finally:
      with self._sync_lock:
        # If the wait was cancelled before acquiring the lock, the lock is not
        # owned
        _ = self._owners.pop(waiter_id, None)

        del self._waiters[waiter_id]

        self._update()

  def _is_blocking(self, waiter: SmartLockWaiter, owner: SmartLockOwner):
    # TODO: Handle scopes
    return (waiter.mode == 'exclusive') or (owner.waiter.mode == 'exclusive')

  def _update(self):
    # The sync lock is assumed to be held

    for waiter_id, waiter in self._waiters.items():
      if not any(self._is_blocking(waiter, owner) for owner in self._owners.values()):
        waiter.future.get_loop().call_soon_threadsafe(waiter.future.set_result, None)

        self._owners[waiter_id] = SmartLockOwner(
          context_scope=None, # TODO: Actually do something better
          waiter=waiter,
        )

        break
    else:
      for waiter_id, waiter in self._waiters.items():
        if waiter.weak:
          continue

        if not any((not waiter.weak) and self._is_blocking(waiter, owner) for owner in self._owners.values()):
          pass

        weak_owners = [owner for owner in self._owners.values() if self._is_blocking(waiter, owner)]

        for weak_owner in weak_owners:
          scope = weak_owner.context_scope

          if (scope is not None) and (scope.cancellation_count == 0):
            scope.cancel()

        break
