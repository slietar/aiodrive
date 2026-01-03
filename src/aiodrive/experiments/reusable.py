import functools
from collections.abc import Awaitable, Callable
from types import CoroutineType

from ..modules.awaitable import ConcreteAwaitable


def reusable[**P, T](func: Callable[P, CoroutineType]):
  @functools.wraps(func)
  def new_func(*args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
    def _await():
      it = func(*args, **kwargs).__await__()
      yield from it
      return it.close()

    return ConcreteAwaitable(_await) # type: ignore

  return new_func



if __name__ == '__main__':
  import asyncio

  @reusable
  async def a():
    return 34

  async def main():
    coro = a()

    print(await coro)
    print(await coro)

  asyncio.run(main())
