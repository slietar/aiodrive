import contextlib
from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager
from typing import overload

from .shield import cleanup_shield
from .wait import try_all, wait_all


@overload
def concurrent_contexts(managers: tuple[()], /) -> AbstractAsyncContextManager[tuple[()]]:
    ...

@overload
def concurrent_contexts[T1](managers: tuple[AbstractAsyncContextManager[T1]], /) -> AbstractAsyncContextManager[tuple[T1]]:
    ...

@overload
def concurrent_contexts[T1, T2](managers: tuple[AbstractAsyncContextManager[T1], AbstractAsyncContextManager[T2]], /) -> AbstractAsyncContextManager[tuple[T1, T2]]:
    ...

@overload
def concurrent_contexts[T1, T2, T3](managers: tuple[AbstractAsyncContextManager[T1], AbstractAsyncContextManager[T2], AbstractAsyncContextManager[T3]], /) -> AbstractAsyncContextManager[tuple[T1, T2, T3]]:
    ...

@overload
def concurrent_contexts[T](managers: Iterable[AbstractAsyncContextManager[T]], /) -> AbstractAsyncContextManager[tuple[T, ...]]:
    ...

@contextlib.asynccontextmanager
async def concurrent_contexts(managers: Iterable[AbstractAsyncContextManager], /) -> AsyncIterator[tuple]:
    """
    Enter multiple asynchronous context managers concurrently.

    Context managers are entered and exited concurrently.

    If any context manager fails to enter, the pending context managers are
    cancelled and the entered ones are exited. If any context manager fails to
    exit, the context manager waits for all entered context managers to exit
    without cancelling pending ones.

    Parameters
    ----------
    managers
        An iterable of asynchronous context managers to enter concurrently.

    Returns
    -------
    AbstractAsyncContextManager[tuple]
        An asynchronous context manager that yields a tuple of the results from
        entering each context manager. The order is maintained.
    """

    # Some managers may fail to enter, so we must track which ones succeeded.
    open_managers = list[AbstractAsyncContextManager]()

    async def enter_context(manager: AbstractAsyncContextManager):
        context_value = await manager.__aenter__()
        open_managers.append(manager)
        return context_value

    try:
        yield tuple(await try_all(enter_context(manager) for manager in managers))
    finally:
        await cleanup_shield(wait_all(manager.__aexit__(None, None, None) for manager in open_managers))


__all__ = [
    'concurrent_contexts',
]
