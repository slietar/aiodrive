from asyncio import Task
from collections.abc import Awaitable
from typing import Never


type DaemonAwaitable = Awaitable[Never]
type DaemonTask = Task[Never]


class DaemonReturnError(Exception):
  pass


async def ensure_daemon(awaitable: DaemonAwaitable, /):
  """
  Ensure that the provided awaitable never returns.

  Parameters
  ----------
  awaitable
    The awaitable.

  Raises
  ------
  DaemonReturnError
    If the awaitable returns.
  """

  await awaitable
  raise DaemonReturnError


__all__ = [
  'DaemonAwaitable',
  'DaemonReturnError',
  'DaemonTask',
  'ensure_daemon',
]
