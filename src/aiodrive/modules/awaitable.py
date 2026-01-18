import inspect
from asyncio import Future
from collections.abc import Awaitable, Callable, Generator
from dataclasses import dataclass
from typing import Any, Never


@dataclass(slots=True)
class ConcreteAwaitable[T]:
  """
  An awaitable created from an `__await__` function.
  """

  __await__: Callable[[], Generator[Any, Any, T]]


async def possibly_await[T](obj: Awaitable[T] | T, /) -> T:
  """
  Wait for the given object if it is awaitable, or otherwise return it as is.

  Parameters
  ----------
  obj
    The object to possibly await.

  Returns
  -------
  T
    The result of the awaitable, or the object itself if it was not awaitable.
  """

  if inspect.isawaitable(obj):
    return await obj

  return obj


async def wait_forever() -> Never: # type: ignore
  """
  Wait indefinitely.
  """

  await Future()


__all__ = [
  'ConcreteAwaitable',
  'possibly_await',
  'wait_forever',
]
