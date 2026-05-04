import asyncio
import inspect
from asyncio import Future, Task
from collections.abc import Awaitable, Callable, Coroutine, Generator
from dataclasses import dataclass
from typing import Any, Never

from .cancel import cancel_task, suppress


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


async def terminate(obj: Awaitable[object], /):
  """
  Terminate the given awaitable, disposing of it as soon as possible.

  Parameters
  ----------
  obj
    The awaitable to terminate.
  """

  match obj:
    case Coroutine():
      obj.close()
    case Task():
      await cancel_task(obj)
    case Future():
      obj.cancel('Terminating awaitable')

      with suppress(asyncio.CancelledError):
        await obj
    case _:
      await obj


async def wait_forever() -> Never: # type: ignore
  """
  Wait indefinitely.
  """

  loop = asyncio.get_running_loop()
  await loop.create_future()


__all__ = [
  'ConcreteAwaitable',
  'possibly_await',
  'terminate',
  'wait_forever',
]
