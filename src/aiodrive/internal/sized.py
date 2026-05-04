from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Iterable,
    Sized,
)
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None:
        ...

@runtime_checkable
class SupportsAclose(Protocol):
    async def aclose(self) -> None:
        ...


class CloseableSizedAsyncIterator[T](AsyncIterator[T], Sized, SupportsAclose, Protocol):
    ...

class CloseableAsyncIterator[T](AsyncIterator[T], SupportsAclose, Protocol):
    ...

class SizedAsyncIterable[T](AsyncIterable[T], Sized, Protocol):
    ...

class SizedIterable[T](Iterable[T], Sized, Protocol):
    ...


class aiterator_impl[T]:
    __slots__ = ("__len__", "_aiterator", "aclose")

    def __init__(self, aiterator: AsyncIterator[T], /, *, length: Optional[int] = None):
        self._aiterator = aiterator

        if isinstance(aiterator, SupportsAclose):
            self.aclose = aiterator.aclose

        if length is not None:
            self.__len__ = lambda: length

    def __aiter__(self):
        return self

    def __anext__(self):
        return self._aiterator.__anext__()

    @classmethod
    def from_iterable(cls, iterable: SizedAsyncIterable[T], /):
        return cls(aiter(iterable), length=len(iterable))
