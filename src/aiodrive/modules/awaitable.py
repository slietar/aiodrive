from asyncio import Future
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any, Never


@dataclass(slots=True)
class ConcreteAwaitable[T]:
  """
  An awaitable created from an `__await__` function.
  """

  __await__: Callable[[], Generator[Any, Any, T]]


async def wait_forever() -> Never: # type: ignore
  """
  Wait indefinitely.
  """

  await Future()


__all__ = [
  'ConcreteAwaitable',
  'wait_forever',
]
