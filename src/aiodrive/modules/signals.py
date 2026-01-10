import asyncio
import contextlib
import functools
import itertools
import signal
from asyncio import Event, Future
from collections.abc import Callable, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from signal import Signals as SignalCode
from typing import NewType, Optional, cast

from .scope import use_scope


@dataclass(slots=True)
class SignalHandledException(Exception):
    signal: signal.Signals


ListenerId = NewType("ListenerId", int)

SIGNAL_LISTENING_VAR = ContextVar[list[ListenerId]]("SIGNAL_LISTENING_VAR", default=[cast(ListenerId, 0)])

@dataclass(slots=True)
class ListenerInfo:
    callback: Callable
    descendant_count: int

listener_id_counter = itertools.count(start=1)
signal_listeners = dict[SignalCode, dict[ListenerId, ListenerInfo]]()


@contextlib.contextmanager
def handle_signal(raw_signal_code: Sequence[SignalCode] | SignalCode, /) -> Iterator[None]:
    """
    Handle specified signals by cancelling the current task.

    If any of the specified signals is received, the current task is cancelled
    and upon exiting the context manager, a `SignalHandledException` is raised.
    Additional signals received while waiting for the context manager cause the
    current task to be cancelled again.

    If control is never yielded back to the event loop after a signal is
    received, for instance because the code inside the context manager is
    blocking, the current task is not cancelled but the exception is still
    raised.

    No other signal listeners for the same codes may be registered for the
    current event loop.

    Parameters
    ----------
    raw_signal_code
        The signal code or codes to handle e.g. `signal.Signals.SIGINT`.

    Raises
    ------
    SignalHandledException
        If a signal is handled and no other other cancellation of the current
        task occured. The attribute `signal` contains the last handled signal
        code.
    """

    if isinstance(raw_signal_code, Sequence):
        signal_codes = list(raw_signal_code)
    else:
        signal_codes = [raw_signal_code]

    loop = asyncio.get_running_loop()

    ancestor_ids = SIGNAL_LISTENING_VAR.get()
    self_id = ListenerId(listener_id_counter.__next__())

    SIGNAL_LISTENING_VAR.set([*ancestor_ids, self_id])

    exited = False
    handled_signal_code: Optional[SignalCode] = None

    def callback(signal_code: SignalCode):
        nonlocal handled_signal_code

        # Store the last handled signal code
        handled_signal_code = signal_code

        if not exited:
            scope.cancel()

    def signal_handler(signal_code: SignalCode):
        for listener_info in signal_listeners[signal_code].values():
            if listener_info.descendant_count == 0:
                listener_info.callback()

    for signal_code in signal_codes:
        if signal_code not in signal_listeners:
            signal_listeners[signal_code] = {}

            loop.add_signal_handler(
                signal_code,
                functools.partial(signal_handler, signal_code),
            )

        signal_listeners[signal_code][self_id] = ListenerInfo(
            callback=functools.partial(callback, signal_code),
            descendant_count=0,
        )

        for ancestor_id in ancestor_ids:
            if (ancestor_info := signal_listeners[signal_code].get(ancestor_id)) is not None:
                ancestor_info.descendant_count += 1

    try:
        with use_scope() as scope:
            yield
    finally:
        SIGNAL_LISTENING_VAR.set(ancestor_ids)

        for signal_code in signal_codes:
            x_signal_listeners = signal_listeners[signal_code]

            del x_signal_listeners[self_id]

            if not x_signal_listeners:
                del signal_listeners[signal_code]
                loop.remove_signal_handler(signal_code)
            else:
                for ancestor_id in ancestor_ids:
                    if (ancestor_info := x_signal_listeners.get(ancestor_id)) is not None:
                        ancestor_info.descendant_count -= 1

        exited = True

    if handled_signal_code is not None:
        raise SignalHandledException(handled_signal_code)


async def wait_for_signal(signal_code: Sequence[SignalCode] | SignalCode, /):
    """
    Wait for any of the specified signals to be received.

    No other signal listeners for the same codes may be registered for the
    current event loop.

    Parameters
    ----------
    signal_codes
        The signal code or codes to wait for e.g. `signal.Signals.SIGINT`.
    """

    if isinstance(signal_code, Sequence):
        signal_codes = list(signal_code)
    else:
        signal_codes = [signal_code]

    loop = asyncio.get_running_loop()
    future = Future[None]()

    def handler():
        if not future.done():
            future.set_result(None)

    for rec_signal_code in signal_codes:
        loop.add_signal_handler(rec_signal_code, handler)

    try:
        await future
    finally:
        for rec_signal_code in signal_codes:
            loop.remove_signal_handler(rec_signal_code)


async def watch_signal(signal_code: Sequence[SignalCode] | SignalCode, /):
    """
    Watch for any of the specified signals to be received.

    If a signal occurs in between two iterations, the next iteration will
    immediately yield.

    The generator must be closed so that the signal handlers are removed.

    No other signal listeners for the same codes may be registered for the
    current event loop.

    Parameters
    ----------
    signal_codes
        The signal code or codes to watch for e.g. `signal.Signals.SIGINT`.

    Yields
    ------
    None
        Each time any of the specified signals is received.
    """

    if isinstance(signal_code, Sequence):
        signal_codes = list(signal_code)
    else:
        signal_codes = [signal_code]

    loop = asyncio.get_running_loop()
    event = Event()

    for rec_signal_code in signal_codes:
        loop.add_signal_handler(rec_signal_code, event.set)

    try:
        while True:
            await event.wait()
            event.clear()

            yield
    finally:
        for rec_signal_code in signal_codes:
            loop.remove_signal_handler(rec_signal_code)


__all__ = [
    "SignalHandledException",
    "handle_signal",
    "wait_for_signal",
    "watch_signal",
]
