from collections.abc import AsyncIterable, Sized
from typing import Optional, Protocol, runtime_checkable


class CloseableSizedAsyncIterable[T](AsyncIterable[T], Sized, Protocol):
    ...


@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None:
        ...

@runtime_checkable
class SupportsAclose(Protocol):
    async def aclose(self) -> None:
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


# class sized_iter[T]:
#     _iterable: Iterable[T]
#     length: int

#     def __iter__(self):
#         return iter(self._iterable)

#     def __len__(self):
#         return self.length

#     def close(self):
#         if inspect.isgenerator(self._iterable):
#             self._iterable.close()
