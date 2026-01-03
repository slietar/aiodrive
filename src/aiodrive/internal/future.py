import asyncio
from asyncio import Future
from collections.abc import Awaitable


# Alias for asyncio.ensure_future with correct typing
def ensure_future[T](obj: Awaitable[T], /) -> Future[T]:
  return asyncio.ensure_future(obj)
