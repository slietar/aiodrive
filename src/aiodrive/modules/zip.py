import inspect
from collections.abc import AsyncIterable

from .shield import cleanup_shield
from .wait import try_all, wait_all


# Unlike input iterables, does not support parallel calls to __anext__
# No strict option because that would cause delays

async def zip_concurrently[T](*iterables: AsyncIterable[T]) -> AsyncIterable[tuple[T, ...]]:
  """
  Zip multiple async iterables together, yielding tuples of items from each
  iterable.

  If one of the iterators raises an exception or is exhausted, all remaining
  queries to iterators are cancelled, and then all generator iterators are
  closed. Items obtained from completed queries are discarded. If an exception
  is raised while closing a generator, it does not cause the cancellation of the
  closure of other generators.

  Parameters
  ----------
  iterables
    The async iterables to zip together.

  Yields
  ------
  tuple
    Tuples of items from each iterable.
  """

  iterators = [iterable.__aiter__() for iterable in iterables]

  try:
    while True:
      try:
        items = await try_all(it.__anext__() for it in iterators)
      except* StopAsyncIteration as e:
        raise StopAsyncIteration from e # Mmmmh not sure

      yield tuple(items)
  finally:
    await cleanup_shield(wait_all(iterator.aclose() for iterator in iterators if inspect.isasyncgen(iterator)))


__all__ = [
  'zip_concurrently',
]
