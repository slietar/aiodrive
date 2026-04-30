import contextlib
import fcntl
import select
from os import PathLike
from pathlib import Path

from .button import Button
from .kqueue import KqueueEventManager


NOTE_FUNLOCK = 0x100


@contextlib.asynccontextmanager
async def flock_kqueue(path: PathLike | str, *, exclusive: bool):
    """
    Acquire an flock lock, using kqueue to wait for the lock to be released.

    The lock must not be acquired elsewhere in the same process.

    Parameters
    ----------
    path
        The path to the lock file.
    exclusive
        Whether to acquire an exclusive lock.

    Returns
    -------
    AbstractAsyncContextManager[None]
    """

    with Path(path).open("wb") as file:
        try:
            fcntl.flock(file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            button = Button()

            def callback(kevent: select.kevent):
                button.press()

            with KqueueEventManager(callback) as manager:
                manager.update([
                    select.kevent(
                        file,
                        filter=select.KQ_FILTER_VNODE,
                        flags=(select.KQ_EV_ADD | select.KQ_EV_CLEAR),
                        fflags=NOTE_FUNLOCK,
                    ),
                ])

                button.press()

                while True:
                    try:
                        fcntl.flock(file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        break

                    await button

        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


__all__ = [
    "flock_kqueue",
]
