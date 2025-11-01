import asyncio
from collections import namedtuple
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


@dataclass(slots=True)
class WatchedInfo:
    fd: int
    path: Path

@contextlib.asynccontextmanager
async def watch_path(
    raw_path: PathLike | str,
    callback: Callable[[Literal['create', 'delete', 'write']], None],
    /,
):
    # TODO: Docs + error handling + __all__

    target_path = Path(raw_path).resolve()
    watched: Optional[WatchedInfo] = None

    def internal_callback(event: select.kevent):
        nonlocal watched
        assert watched is not None

        watching_directory = watched.path != target_path

        if (event.fflags & select.KQ_NOTE_WRITE) > 0:
            if watching_directory:
                # The target file was potentially added to the watched directory
                update(watched.path / target_path.parts[len(watched.path.parts)])
            else:
                callback('write')

        if (event.fflags & (select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME)) > 0:
            new_path = watched.path.parent
            os.close(watched.fd)
            watched = None

            if watching_directory:
                # The watched directory was deleted or renamed
                pass
            else:
                callback('delete')

            update(new_path)

    def update(guess_path: Path, /):
        nonlocal watched

        attempted_fd = None
        attempted_path = guess_path

        while True:
            print("Starting update loop")

            while True:
                print(f"Attempting to watch: {attempted_path}")

                if (watched is not None) and (attempted_path == watched.path):
                    print("  Skipping")
                    return

                try:
                    new_fd = os.open(
                        attempted_path,
                        os.O_RDONLY | (os.O_DIRECTORY if attempted_path != target_path else 0),
                    )
                except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
                    attempted_path = attempted_path.parent

                    if attempted_fd is not None:
                        break
                else:
                    if attempted_fd is not None:
                        os.close(attempted_fd)

                    attempted_fd = new_fd

                    if attempted_path != target_path:
                        attempted_path /= target_path.parts[len(attempted_path.parts)]
                    else:
                        break

            watched = WatchedInfo(fd=attempted_fd, path=attempted_path)

            manager.update([
                select.kevent(
                    watched.fd,
                    filter=select.KQ_FILTER_VNODE,
                    flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
                    fflags=(select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME | select.KQ_NOTE_WRITE),
                ),
            ])

            if watched.path == target_path:
                callback('create')

    try:
        async with KqueueEventManager(internal_callback) as manager:
            update(target_path)
            yield
    finally:
        if watched is not None:
            os.close(watched.fd)


async def main():
    async with watch_path('w/test1.txt', print):
        await asyncio.Future()

asyncio.run(main())
