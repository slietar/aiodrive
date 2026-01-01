import asyncio
import contextlib
import select
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class KqueueEventManagerContext:
    update: Callable[[Iterable[select.kevent]], None]
    """
    Update kqueue event registrations.

    Parameters
    ----------
    events
        An iterable of kqueue events to register.
    """


@contextlib.asynccontextmanager
async def KqueueEventManager(
    callback: Callable[[select.kevent], None],
    /,
):
    """
    Create a context manager for receiving kqueue events.

    Parameters
    ----------
    callback
        A callback that is called when a kqueue event is received.

    Returns
    -------
    AbstractAsyncContextManager[_KqueueEventManager]
        A context manager that provides an update function to register kqueue
        event registrations.
    """

    kq = select.kqueue()
    kq_fd = kq.fileno()

    def update(events: Iterable[select.kevent]):
        kq.control(events, 0, None)

    def internal_callback():
        event = kq.control(None, 1, 0)
        callback(event[0])

    loop = asyncio.get_running_loop()
    loop.add_reader(kq_fd, internal_callback)

    try:
        yield KqueueEventManagerContext(update)
    finally:
        loop.remove_reader(kq_fd)
        kq.close()


__all__ = [
    "KqueueEventManager",
    "KqueueEventManagerContext",
]
