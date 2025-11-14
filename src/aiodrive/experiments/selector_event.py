import asyncio
import contextlib
import logging
import os
import select
from asyncio import Handle, TimerHandle
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal, Optional

from ..modules.handle import using_pending_daemon_handle


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _KqueueEventManager:
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
        yield _KqueueEventManager(update)
    finally:
        loop.remove_reader(kq_fd)
        kq.close()


@dataclass(slots=True)
class WatchedInfo:
    fd: int
    path: Path

type WatchPathEvent = Literal['create', 'delete', 'write']

@using_pending_daemon_handle
async def watch_path(
    raw_path: PathLike | str,
    /,
    callback: Callable[[WatchPathEvent], None],
    *,
    call_immediately: bool = True,
    debounce_delay: Optional[float] = None,
):
    """
    Watch a single path.

    This function is only supported if kqueue is available.

    Parameters
    ----------
    raw_path
        The path to watch. Can be a file or directory.
    callback
        A callback that is called when the watched path is created, deleted,
        points to a file that has been written to, or points to a directory
        whose child list was modified. The callback is called on the next
        iteration of the event loop. Exiting the context manager cancels any
        pending call.
    call_immediately
        Whether to call the callback immediately if the path exists when
        starting to watch it. The call is performed immediately.
    debounce_delay
        The debounce delay in seconds. If `None`, no debouncing is performed.

    Returns
    -------
    AbstractAsyncContextManager[None]
    """

    callback_handle: Optional[Handle | TimerHandle] = None
    last_reported_exists: Optional[bool] = None
    queued_event: Optional[WatchPathEvent] = None

    loop = asyncio.get_running_loop()

    def eager_callback(event: WatchPathEvent):
        nonlocal callback_handle, last_reported_exists, queued_event
        queued_event = event

        if last_reported_exists is None:
            if call_immediately:
                last_reported_exists = (event == 'create')
                callback(event)

            return

        if (not last_reported_exists) and (queued_event == 'delete'):
            if callback_handle is not None:
                callback_handle.cancel()
                callback_handle = None

            return

        if debounce_delay is not None:
            if callback_handle is not None:
                callback_handle.cancel()

            callback_handle = loop.call_later(debounce_delay, late_callback)
        else:
            callback_handle = loop.call_soon(late_callback)

    def late_callback():
        nonlocal last_reported_exists

        match (last_reported_exists, queued_event):
            case (False, 'create' | 'write'):
                callback('create')
                last_reported_exists = True
            case (False, 'delete'):
                raise RuntimeError('Unreachable')
            case (True, 'delete'):
                callback('delete')
                last_reported_exists = False
            case (True, 'create' | 'write'):
                callback('write')


    target_path = Path(raw_path).resolve()
    watched: Optional[WatchedInfo] = None

    def internal_callback(event: select.kevent):
        nonlocal watched
        assert watched is not None

        watching_ancestor = watched.path != target_path

        if (event.fflags & (select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME)) > 0:
            if watching_ancestor:
                # The watched directory was deleted or renamed
                pass
            else:
                eager_callback('delete')

            update_down(watched.path.parent)
        elif (event.fflags & select.KQ_NOTE_WRITE) > 0:
            if watching_ancestor:
                # The target file was potentially added to the watched directory
                update_up(watched.path)
            else:
                eager_callback('write')

    def try_open(path: Path, /):
        try:
            return os.open(
                path,
                os.O_RDONLY | (os.O_DIRECTORY if path != target_path else 0),
            )
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None

    def update_down(guess_path_inclusive: Path, /):
        current_path = guess_path_inclusive

        while (fd := try_open(current_path)) is None:
            current_path = current_path.parent

        update_watch(fd, current_path)

    def update_up(guess_path_exclusive: Path, /):
        current_fd: Optional[int] = None
        current_path = guess_path_exclusive

        while current_path != target_path:
            current_path /= target_path.parts[len(current_path.parts)]
            fd = try_open(current_path)

            if fd is None:
                current_path = current_path.parent
                break

            if current_fd is not None:
                os.close(current_fd)

            current_fd = fd

        if current_fd is not None:
            update_watch(current_fd, current_path)

        # If no ancestor or target was added to the currently-watched directory,
        # 'current_fd' is None and there is nothing to change.

    def update_watch(fd: int, path: Path, /):
        nonlocal watched

        if (watched is not None) and (watched.path == path):
            return

        if watched is not None:
            os.close(watched.fd)

        watched = WatchedInfo(fd=fd, path=path)
        logger.debug(f'Watching {watched.path}')

        manager.update([
            select.kevent(
                watched.fd,
                filter=select.KQ_FILTER_VNODE,
                flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
                fflags=(select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME | select.KQ_NOTE_WRITE),
            ),
        ])

        if path.exists():
            if watched.path == target_path:
                eager_callback('create')
            else:
                update_up(watched.path)
        else:
            # The file was deleted between opening and registering
            update_down(path.parent)

    try:
        async with KqueueEventManager(internal_callback) as manager:
            update_down(target_path)
            yield
    finally:
        if callback_handle is not None:
            callback_handle.cancel()

        if watched is not None:
            os.close(watched.fd)


__all__ = [
    'KqueueEventManager',
    'WatchPathEvent',
    'watch_path',
]


if __name__ == "__main__":
    async def main():
        logging.basicConfig(level=logging.DEBUG)

        async with watch_path('playground/a/b/c', print):
            await asyncio.Future()

    asyncio.run(main())
