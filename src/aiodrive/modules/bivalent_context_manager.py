import contextlib
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import AbstractAsyncContextManager, AbstractContextManager


class AbstractBivalentContextManager[T](AbstractContextManager[T], AbstractAsyncContextManager[T]):
  pass


def bivalent_context_manager[**P, T](
  sync_handler: Callable[P, Generator[T]],
  async_handler: Callable[P, AsyncGenerator[T]],
  /,
) -> Callable[P, AbstractBivalentContextManager[T]]:
  """
  Create a function that returns a context manager which can be used both
  synchronously and asynchronously.

  Parameters
  ----------
  sync_handler
    A function that creates a synchronous context manager.
  async_handler
    A function that creates an asynchronous context manager.

  Returns
  -------
  Callable[P, AbstractBivalentContextManager[T]]
  """

  async_manager_factory = contextlib.asynccontextmanager(async_handler)
  sync_manager_factory = contextlib.contextmanager(sync_handler)

  class DoubleContextManager:
    def __init__(self, *args: P.args, **kwargs: P.kwargs):
      self._args = args
      self._kwargs = kwargs

    async def __aenter__(self) -> T:
      self._async_manager = async_manager_factory(*self._args, **self._kwargs)
      return await self._async_manager.__aenter__()

    async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
      return await self._async_manager.__aexit__(exc_type, exc_value, traceback)

    def __enter__(self) -> T:
      self._sync_manager = sync_manager_factory(*self._args, **self._kwargs)
      return self._sync_manager.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
      return self._sync_manager.__exit__(exc_type, exc_value, traceback)

  return DoubleContextManager # type: ignore


__all__ = [
  'AbstractBivalentContextManager',
  'bivalent_context_manager',
]
