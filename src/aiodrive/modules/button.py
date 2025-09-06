import asyncio
from asyncio import Future
from dataclasses import dataclass, field


@dataclass(slots=True)
class Button:
  """
  A class that wakes up registered waiters when called.

  The functionality of this class is similar to an asyncio Event that resets
  itself immediately after being set.
  """

  _future: Future[None] = field(default_factory=Future, init=False, repr=False)

  def press(self):
    self._future.set_result(None)
    self._future = Future()

  def __await__(self):
    return asyncio.shield(self._future).__await__()


@dataclass(slots=True)
class Cargo[T]:
  """
  A class that wakes up registered waiters with a value when called with that
  value.
  """

  _future: Future[T] = field(default_factory=Future, init=False, repr=False)

  def __call__(self, value: T, /):
    self._future.set_result(value)
    self._future = Future()

  def __await__(self):
    return asyncio.shield(self._future).__await__()


__all__ = [
  'Button',
  'Cargo',
]
