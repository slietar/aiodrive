import functools
from asyncio import Lock
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class NestableLock:
    """
    A lock that can be acquired multiple times as long as the `contextvars`
    context is the same.

    This is more or less an async equivalent of `threading.RLock`.
    """

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

    async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
        level = self._context_var.get()

        if level == 1:
            self._lock.release()

        self._context_var.set(level - 1)


__all__ = [
    'NestableLock',
]
