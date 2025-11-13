from collections.abc import Awaitable, Callable
import contextlib

from .shield import ShieldContext


@contextlib.asynccontextmanager
async def cleaned_up(callback: Callable[[], Awaitable[None]], /):
  """
  Create a context manager that calls the given async callback when exiting the
  context.

  The callback is shielded from exactly one cancellation with respect to when
  the context was entered.

  Parameters
  ----------
  callback
    An async function to be called when exiting the context.

  Returns
  -------
  AbstractAsyncContextManager[None]
  """

  context = ShieldContext()

  try:
    yield
  finally:
    await context.shield(callback())


__all__ = [
  'cleaned_up',
]
