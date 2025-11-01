import asyncio
import contextlib
from dataclasses import dataclass
import select
from collections.abc import Callable, Container, Iterable
from os import PathLike
from pathlib import Path
from typing import IO, Literal


# Only works on macOS - Linux uses inotify
# This is a _bridge_ implementation for kqueue-based file watching


@dataclass(slots=True)
class EventManager:
    update: Callable[[Iterable[select.kevent]], None]


@contextlib.asynccontextmanager
async def watch_for_kqueue_events(
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
