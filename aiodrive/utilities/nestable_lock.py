import functools
from asyncio import Lock
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class NestableLock:
    _context_var: ContextVar[int] = field(
        default_factory=functools.partial(ContextVar, "nestable_lock", default=0),
        init=False,
        repr=False,
    )

    _lock: Lock = field(
        default_factory=Lock,
        init=False,
        repr=False,
    )

    async def __aenter__(self):
        level = self._context_var.get()

        if level == 0:
            await self._lock.acquire()

        self._context_var.set(level + 1)

    async def __aexit__(self, exc_type, exc_value, traceback):
        level = self._context_var.get()

        if level == 1:
            self._lock.release()

        self._context_var.set(level - 1)
