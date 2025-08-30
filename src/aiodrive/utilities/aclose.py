from collections.abc import AsyncIterator
import contextlib
import inspect


@contextlib.asynccontextmanager
async def ensure_aclosing(iterator: AsyncIterator, /):
  if inspect.isasyncgen(iterator):
    async with contextlib.aclosing(iterator):
      yield
  else:
    yield
