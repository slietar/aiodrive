import contextlib

from ..internal.sized import SupportsAclose, SupportsClose


@contextlib.contextmanager
def auto_closing(obj: object, /):
  """
  Create a context manager that calls the `close` method, if any, on the
  provided object upon exit.

  Parameters
  ----------
  obj
    The object to automatically close.

  Returns
  -------
  AbstractContextManager[None]
  """

  try:
    yield None
  finally:
    if isinstance(obj, SupportsClose):
      obj.close()


@contextlib.asynccontextmanager
async def auto_aclosing(obj: object, /):
  """
  Create an async context manager that calls the `aclose` method, if any, on the
  provided object upon exit.

  Parameters
  ----------
  obj
    The object to automatically close.

  Returns
  -------
  AbstractAsyncContextManager[None]
  """

  try:
    yield obj
  finally:
    if isinstance(obj, SupportsAclose):
      await obj.aclose()


__all__ = [
  'auto_aclosing',
  'auto_closing',
]
