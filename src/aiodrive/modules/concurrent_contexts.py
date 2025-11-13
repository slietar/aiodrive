import contextlib
from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager
from typing import overload

from .cleanup import cleaned_up
from .wait import wait_all


@overload
def concurrent_contexts() -> AbstractAsyncContextManager[tuple[()]]:
    ...

@overload
def concurrent_contexts[T1](
    manager1: AbstractAsyncContextManager[T1],
    /,
) -> AbstractAsyncContextManager[tuple[T1]]:
    ...

@overload
def concurrent_contexts[T1, T2](
    manager1: AbstractAsyncContextManager[T1],
    manager2: AbstractAsyncContextManager[T2],
    /,
) -> AbstractAsyncContextManager[tuple[T1, T2]]:
    ...

@overload
def concurrent_contexts[T1, T2, T3](
    manager1: AbstractAsyncContextManager[T1],
    manager2: AbstractAsyncContextManager[T2],
    manager3: AbstractAsyncContextManager[T3],
    /,
) -> AbstractAsyncContextManager[tuple[T1, T2, T3]]:
    ...

@overload
def concurrent_contexts[T](*managers: AbstractAsyncContextManager[T]) -> AbstractAsyncContextManager[tuple[T, ...]]:
    ...

@overload
def concurrent_contexts[T](managers: Iterable[AbstractAsyncContextManager[T]], /) -> AbstractAsyncContextManager[tuple[T, ...]]:
    ...

@contextlib.asynccontextmanager
async def concurrent_contexts(*managers: AbstractAsyncContextManager | Iterable[AbstractAsyncContextManager]) -> AsyncIterator[tuple]:
    """
    Enter multiple asynchronous context managers concurrently.

    Context managers are entered and exited concurrently.

    If any context manager fails to enter, the pending context managers are
    cancelled and the entered ones are exited. If any context manager fails to
    exit, the context manager waits for all entered context managers to exit
    without cancelling pending ones.

    Because all context managers are entered and exited concurrently, they are
    not provided with the potential exception of their context. Context managers
    that depend on the exception usually provided in `__exit__()`, such as that
    returned by `contextlib.suppress()`, do not work as expected. Similarly,
    context managers that update a global state, such as
    `contextvars.ContextVar.set` which returns a `contextvars.Token`, may not
    work as expected if the state is read or written to by another context being
    entered or exited concurrently.

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

    if managers and isinstance(managers[0], Iterable):
        assert len(managers) == 1
        effective_managers = tuple(managers[0])
    else:
        effective_managers: tuple[AbstractAsyncContextManager, ...] = managers # type: ignore

    # Some managers may fail to enter, so we must track which ones succeeded.
    open_managers = list[AbstractAsyncContextManager]()

    async def enter_context(manager: AbstractAsyncContextManager):
        context_value = await manager.__aenter__()
        open_managers.append(manager)
        return context_value

    async def exit_contexts():
        await wait_all(manager.__aexit__(None, None, None) for manager in open_managers)

    async with cleaned_up(exit_contexts):
        yield tuple(await wait_all(enter_context(manager) for manager in effective_managers))


__all__ = [
    'concurrent_contexts',
]
