import asyncio
import contextlib
import functools
import types
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable
from types import CoroutineType
from typing import Any, Optional

from .event_loop import set_event_loop
from .future_state import FutureState


def prime[T](awaitable: Awaitable[T], /, *, loop: Optional[AbstractEventLoop] = None) -> Awaitable[T]:
  """
  Prime an awaitable such that as much code as possible is executed immediately.
  This is akin to creating tasks with `asyncio.eager_task_factory` as the task
  factory.

  If the returned awaitable is not awaited, the closure of the original
  awaitable is only performed during garbage collection. If the event loop is
  closed, async cleanup operations will fail.

  Parameters
  ----------
  awaitable
    The awaitable to prime.
  loop
    The event loop to use while priming. If `None`, the current running loop
    must exist and is used.

  Returns
  -------
  Awaitable[T]
    An awaitable that returns the result of the provided awaitable.
  """

  # Ensure we have a running loop if none was provided
  if loop is None:
    _ = asyncio.get_running_loop()

  generator = awaitable.__await__()

  with set_event_loop(loop) if loop is not None else contextlib.nullcontext():
    hint = FutureState.absorb_lambda(generator.send, None)

  @types.coroutine
  def inner():
    try:
      value = hint.apply()
    except StopIteration as e:
      return e.value

    while True:
      try:
        yield value
      except BaseException as e:
        try:
          value = generator.throw(e)
        except StopIteration as e:
          return e.value
      else:
        try:
          value = generator.send(value)
        except StopIteration as e:
          return e.value

  return inner()


def primed[**P, R](func: Callable[P, Awaitable[R]], /) -> Callable[P, CoroutineType[Any, Any, R]]:
  """
  Decorate the given function such that it returns a primed awaitable.
  """

  @functools.wraps(func)
  def wrapper(*args: P.args, **kwargs: P.kwargs):
    awaitable = prime(func(*args, **kwargs))

    async def new_func():
      return await awaitable

    return new_func()

  return wrapper


__all__ = [
  'prime',
  'primed',
]
