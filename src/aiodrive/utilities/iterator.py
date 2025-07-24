from collections.abc import AsyncIterable, AsyncIterator, Iterable


def ensure_aiter[T](iterable: AsyncIterable[T] | Iterable[T]) -> AsyncIterator[T]:
    if hasattr(iterable, "__aiter__"):
        return aiter(iterable)  # type: ignore
    else:
        async def create_aiter():
            for item in iterable:  # type: ignore
                yield item

        return create_aiter()
