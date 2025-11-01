import asyncio
import contextlib
import os
import select
from collections.abc import Callable, Container, Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import IO, Literal, Optional


# Only works on macOS - Linux uses inotify
# This is a _bridge_ implementation for kqueue-based file watching


@dataclass(slots=True)
class EventManager:
    update: Callable[[Iterable[select.kevent]], None]


@contextlib.asynccontextmanager
async def KqueueEventManager(
    callback: Callable[[select.kevent], None],
    /,
):
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
        yield EventManager(update)

    finally:
        loop.remove_reader(kq_fd)
        kq.close()


# type EventType = Literal[
#     'attrib',
#     'delete',
#     'extend',
#     'link',
#     'rename',
#     'revoke',
#     'write',
# ]

# @contextlib.asynccontextmanager
# async def watch_file(file: IO, callback: Callable[[str], None], /, *, events: Container[EventType]):
#     """
#     Watch a file for changes using kqueue.

#     Parameters
#     ----------
#     path
#         The path to the file to watch.
#     callback
#         The callback to call when an event occurs.
#     events
#         The events to watch for. Possible values are:
#         - `attrib`: File or directory attributes changed.
#         - `delete`: File or directory was deleted.
#         - `extend`: File was extended.
#         - `rename`: File or directory was renamed.
#     """

#     def internal_callback(event: select.kevent):
#         print(event.data, event.udata)
#         # if (event.fflags & select.KQ_NOTE_WRITE) > 0:

#     fflags = 0

#     # if 'attrib' in events:
#     #     fflags |= select.KQ_NOTE_ATTRIB
#     # if 'delete' in events:
#     #     fflags |= select.KQ_NOTE_DELETE

#     kev = select.kevent(
#         file.fileno(),
#         filter=select.KQ_FILTER_VNODE,
#         flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
#         fflags=(select.KQ_NOTE_RENAME),
#         # fflags=(select.KQ_NOTE_RENAME | select.KQ_NOTE_ATTRIB | select.KQ_NOTE_DELETE | select.KQ_NOTE_EXTEND | select.KQ_NOTE_LINK | select.KQ_NOTE_REVOKE | select.KQ_NOTE_WRITE),
#     )

#     async with watch_for_kqueue_events([kev], internal_callback):
#         yield


@contextlib.asynccontextmanager
async def watch_path(
    raw_path: PathLike | str,
    callback: Callable[[Literal['create', 'delete', 'write']], None],
    /,
):
    target_path = Path(raw_path).resolve()

    fd: Optional[int] = None
    watched_path = target_path
    # missing_parts = list[str]()

    def internal_callback(event: select.kevent):
        watching_directory = watched_path != target_path

        if (event.fflags & select.KQ_NOTE_WRITE) > 0:
            if watching_directory:
                # A node was potentially added to the watched directory
                update(direction_down=False)
            else:
                callback('write')

        if (event.fflags & (select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME)) > 0:
            if watching_directory:
                # The watched directory was deleted or renamed
                pass
            else:
                callback('delete')

            update(direction_down=True)

    def update(*, direction_down: bool):
        nonlocal watched_path
        nonlocal fd

        attempted_path = watched_path

        if fd is not None:
            os.close(fd)
            fd = None

        while True:
            print(f"Attempting to watch: {attempted_path}")

            try:
                new_fd = os.open(
                    attempted_path,
                    os.O_RDONLY | (os.O_DIRECTORY if attempted_path != target_path else 0),
                )
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
                if fd is not None:
                    # Done searching
                    break

                attempted_path = attempted_path.parent
            else:
                if fd is not None:
                    os.close(fd)

                fd = new_fd
                watched_path = attempted_path

                if attempted_path != target_path:
                    attempted_path /= target_path.parts[len(attempted_path.parts)]
                else:
                    break


        # assert fd is not None

        if watched_path == target_path:
            callback('create')

        manager.update([
            select.kevent(
                fd,
                filter=select.KQ_FILTER_VNODE,
                flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
                fflags=(select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME | select.KQ_NOTE_WRITE),
            ),
        ])

    try:
        async with KqueueEventManager(internal_callback) as manager:
            update(direction_down=True)
            yield
    finally:
        if fd is not None:
            os.close(fd)


# async def main():
#     async with watch_path('w/test1.txt', print):
#         await asyncio.Future()

# asyncio.run(main())
