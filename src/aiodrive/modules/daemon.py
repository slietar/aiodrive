from asyncio import Task
from collections.abc import Awaitable
from typing import Never

from .awaitable import ConcreteAwaitable


type DaemonAwaitable = Awaitable[Never]
type DaemonTask = Task[Never]


class DaemonReturnError(Exception):
  pass


def ensure_daemon(awaitable: DaemonAwaitable, /) -> Awaitable[Never]:
  """
  Create a new awaitable that raises an exception if the given awaitable
  returns.

  Each await of the returned awaitable leads to an await of the given awaitable.
  If the returned awaitable is not awaited, the given awaitable is not awaited.

  Parameters
  ----------
  awaitable
    The awaitable.

  Raises
  ------
  DaemonReturnError
    If the awaitable returns.
  """

  def func():
    yield from awaitable.__await__()
    raise DaemonReturnError

  return ConcreteAwaitable[Never](func)


__all__ = [
  'DaemonAwaitable',
  'DaemonReturnError',
  'DaemonTask',
  'ensure_daemon',
]
