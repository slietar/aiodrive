import contextlib
from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import overload

from ..wait import try_all


@overload
def enter_contexts_concurrently(contexts: tuple[()], /) -> AbstractAsyncContextManager[tuple[()]]:
    ...

@overload
def enter_contexts_concurrently[T1](contexts: tuple[AbstractAsyncContextManager[T1]], /) -> AbstractAsyncContextManager[tuple[T1]]:
    ...

@overload
def enter_contexts_concurrently[T1, T2](contexts: tuple[AbstractAsyncContextManager[T1], AbstractAsyncContextManager[T2]], /) -> AbstractAsyncContextManager[tuple[T1, T2]]:
    ...

@overload
def enter_contexts_concurrently[T1, T2, T3](contexts: tuple[AbstractAsyncContextManager[T1], AbstractAsyncContextManager[T2], AbstractAsyncContextManager[T3]], /) -> AbstractAsyncContextManager[tuple[T1, T2, T3]]:
    ...

@overload
def enter_contexts_concurrently[T](contexts: Iterable[AbstractAsyncContextManager[T]], /) -> AbstractAsyncContextManager[tuple[T, ...]]:
    ...

@contextlib.asynccontextmanager
async def enter_contexts_concurrently(contexts: Iterable[AbstractAsyncContextManager], /) -> AsyncIterator[tuple]:
    async with AsyncExitStack() as stack:
        yield tuple(
            await try_all(stack.enter_async_context(context) for context in contexts)
        )
