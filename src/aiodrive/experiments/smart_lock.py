import asyncio
import contextlib
from asyncio import Future
from dataclasses import dataclass, field
from threading import Lock as ThreadingLock
from threading import Thread
from typing import Literal

from ..modules.scope import Scope, use_scope


@dataclass(slots=True)
class SmartLockWaiter:
  mode: Literal['exclusive', 'shared']
  scope: Literal['none', 'task', 'thread', 'context']
  weak: bool
  future: Future[None]
  thread: Thread


@dataclass(slots=True)
class SmartLockOwner:
  context_scope: Scope
  waiter: SmartLockWaiter


@dataclass(slots=True)
class SmartLock:
  _next_waiter_id: int = field(default=0, init=False, repr=False)
  _sync_lock: ThreadingLock = field(default_factory=ThreadingLock, init=False, repr=False)
  _owners: set[int] = field(default_factory=set, init=False, repr=False)
  _waiters: dict[int, SmartLockWaiter] = field(default_factory=dict, init=False, repr=False)

  @contextlib.asynccontextmanager
  async def use(
    self,
    mode: Literal['exclusive', 'shared'],
    scope: Literal['none', 'task', 'thread', 'context'],
    weak: bool = False,
  ):
    with self._sync_lock:
      waiter_id = self._next_waiter_id
      self._next_waiter_id += 1

      waiter = SmartLockWaiter(
        mode=mode,
        scope=scope,
        weak=weak,
        future=Future[None](),
      )

      self._waiters[waiter_id] = waiter

    try:
      await asyncio.shield(waiter.future)

      async with use_scope() as context_scope:
        owner = SmartLockOwner(
          context_scope=context_scope,
          waiter=waiter,
        )

        self._owners.add(waiter_id)

        yield
    finally:
      del self._waiters[waiter_id]
