import asyncio
import contextlib
import functools
import signal
from asyncio import Future
from collections.abc import Iterator
from dataclasses import dataclass
from signal import Signals as SignalCode
from typing import Optional

from .scope import use_scope


@dataclass(slots=True)
class SignalHandledException(Exception):
    signal: signal.Signals


@contextlib.contextmanager
def handle_signal(*signal_codes: SignalCode) -> Iterator[None]:
    """
    Handle specified signals by cancelling the current task.

    If any of the specified signals is received, the current task is cancelled
    and upon exiting the context manager, a `SignalHandledException` is raised.
    Additional signals received while waiting for the context manager cause the
    current task to be cancelled again.

    No other signal listeners for the same codes may be registered for the
    current event loop.

    Parameters
    ----------
    signal_codes
        The signal codes to handle e.g. `signal.Signals.SIGINT`.

    Raises
    ------
    SignalHandledException
        If a signal is handled and no other other cancellation of the current
        task occured. The attribute `signal` contains the last handled signal
        code.
    """

    loop = asyncio.get_event_loop()

    handled_signal_code: Optional[SignalCode] = None

    def callback(signal_code: SignalCode):
        nonlocal handled_signal_code

        scope.cancel()

        # Store the last handled signal code
        handled_signal_code = signal_code

    for signal_code in signal_codes:
        loop.add_signal_handler(signal_code, functools.partial(callback, signal_code))

    try:
        with use_scope() as scope:
            yield

        if handled_signal_code is not None:
            raise SignalHandledException(handled_signal_code)
    finally:
        for signal_code in signal_codes:
            loop.remove_signal_handler(signal_code)


async def wait_for_signal(*signal_codes: SignalCode):
    """
    Wait for any of the specified signals to be received.

    No other signal listeners for the same codes may be registered for the
    current event loop.

    Parameters
    ----------
    signal_codes
        The signal codes to wait for e.g. `signal.Signals.SIGINT`.
    """

    loop = asyncio.get_event_loop()
    future = Future[None]()

    def handler():
        if not future.done():
            future.set_result(None)

    for signal_code in signal_codes:
        loop.add_signal_handler(signal_code, handler)

    try:
        await future
    finally:
        for signal_code in signal_codes:
            loop.remove_signal_handler(signal_code)


__all__ = [
    'SignalHandledException',
    'handle_signal',
    'wait_for_signal',
]
