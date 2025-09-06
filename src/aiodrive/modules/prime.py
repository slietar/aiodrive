import types
from collections.abc import Awaitable


def prime[T](awaitable: Awaitable[T], /) -> Awaitable[T]:
  """
  Prime an awaitable such that as much code as possible is executed immediately.
  This is akin to creating tasks with `asyncio.eager_task_factory` as the task
  factory.

  It is safe to run this function on a different event loop or thread than the
  one where the returned coroutine is awaited.

  If the returned awaitable is not awaited, the closure of the original
  awaitable is only performed when the event loop is closed.

  Returns
  -------
  Awaitable[T]
    An awaitable that returns the result of the provided awaitable.
  """

  generator = awaitable.__await__()

  try:
    hint = generator.send(None)
  except StopIteration as e:
    hint = e.value
    returned = True
  else:
    returned = False

  @types.coroutine
  def inner():
    if returned:
      return hint

    yield hint
    result = yield from generator
    return result

  return inner()
