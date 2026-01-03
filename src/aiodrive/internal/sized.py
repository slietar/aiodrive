from collections.abc import AsyncIterable, Iterable, Sized
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None:
        ...

@runtime_checkable
class SupportsAclose(Protocol):
    async def aclose(self) -> None:
        ...


class CloseableSizedAsyncIterable[T](AsyncIterable[T], Sized, SupportsAclose, Protocol):
    ...

class CloseableAsyncIterable[T](AsyncIterable[T], SupportsAclose, Protocol):
    ...

class SizedAsyncIterable[T](AsyncIterable[T], Sized, Protocol):
    ...

class SizedIterable[T](Iterable[T], Sized, Protocol):
    ...


class sized_aiter[T]:
    def __init__(self, aiterable: AsyncIterable[T], *, length: Optional[int] = None):
        self._aiterable = aiterable

        if isinstance(aiterable, SupportsAclose):
            self.aclose = aiterable.aclose

        if length is not None:
            self.__len__ = lambda: length

    def __aiter__(self):
        return self._aiterable.__aiter__()
