from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import overload

from .wait import wait


@overload
def zip_concurrently() -> AsyncIterator[tuple[()]]:
  ...

@overload
def zip_concurrently[T1](
  iterable1: AsyncIterable[T1],
  /,
) -> AsyncIterator[tuple[T1]]:
  ...

@overload
def zip_concurrently[T1, T2](
  iterable1: AsyncIterable[T1],
  iterable2: AsyncIterable[T2],
  /,
) -> AsyncIterator[tuple[T1, T2]]:
  ...

@overload
def zip_concurrently[T1, T2, T3](
  iterable1: AsyncIterable[T1],
  iterable2: AsyncIterable[T2],
  iterable3: AsyncIterable[T3],
  /,
) -> AsyncIterator[tuple[T1, T2, T3]]:
  ...

@overload
def zip_concurrently[T](*iterables: AsyncIterable[T]) -> AsyncIterator[tuple[T, ...]]:
  ...

@overload
def zip_concurrently[T](iterables: Iterable[AsyncIterable[T]], /) -> AsyncIterator[tuple[T, ...]]:
  ...

async def zip_concurrently(*iterables: AsyncIterable | Iterable[AsyncIterable]) -> AsyncIterator[tuple]:
  """
  Zip multiple async iterables together, yielding tuples of items from each
  iterable.

  If one of the iterators raises an exception or is exhausted, all remaining
  queries to iterators are cancelled. Items obtained from completed queries are
  discarded.

  Parameters
  ----------
  iterables
    The async iterables to zip together.

  Yields
  ------
  tuple
    Tuples of items from each iterable.
  """

  if iterables and isinstance(iterables[0], Iterable):
    assert len(iterables) == 1
    effective_iterables = iterables[0]
  else:
    effective_iterables: Iterable[AsyncIterable] = iterables # type: ignore

  iterators = [aiter(iterable) for iterable in effective_iterables]

  while True:
    try:
      items = await wait(anext(iterator) for iterator in iterators)
    except* StopAsyncIteration as e:
      raise StopAsyncIteration from e # Mmmmh not sure

    yield tuple(items)


__all__ = [
  'zip_concurrently',
]
