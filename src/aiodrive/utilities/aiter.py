from collections import deque
from collections.abc import AsyncIterable

from .aclose import ensure_aclosing
from .latch import Latch
from .versatile import contextualize


async def buffer_aiter[T](iterable: AsyncIterable[T], /, *, size: int):
  assert size >= 0

  iterator = aiter(iterable)
  queue = deque[T]()
  latch = Latch()

  async def producer():
    while True:
      if len(queue) >= size:
        await latch.wait_unset()

      queue.append(await anext(iterator))
      latch.set()

  async with (
    ensure_aclosing(iterator),
    contextualize(producer()),
  ):
    await latch.wait_set()
    item = queue.popleft()

    if not queue:
      latch.unset()

    yield item
