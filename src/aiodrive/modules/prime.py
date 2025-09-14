import types
from collections.abc import Awaitable

from .future_state import FutureState


def prime[T](awaitable: Awaitable[T], /) -> Awaitable[T]:
  """
  Prime an awaitable such that as much code as possible is executed immediately.
  This is akin to creating tasks with `asyncio.eager_task_factory` as the task
  factory.

  It is safe to run this function on a different event loop or thread than the
  one where the returned coroutine is awaited.

  If the returned awaitable is not awaited, the closure of the original
  awaitable is only performed during garbage collection. If the event loop is
  closed, async cleanup operations will fail.

  Returns
  -------
  Awaitable[T]
    An awaitable that returns the result of the provided awaitable.
  """

  generator = awaitable.__await__()
  hint = FutureState.absorb_lambda(lambda: generator.send(None))

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


__all__ = [
  'prime',
]
