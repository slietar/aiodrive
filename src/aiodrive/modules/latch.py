import asyncio
from asyncio import Future
from dataclasses import dataclass, field


@dataclass(slots=True)
class Latch:
  """
  A class that can be set or unset, and can be waited on state changes.

  This is similar to `asyncio.Event` but allows waiting for both set and unset
  states.
  """

  _future: Future[None] = field(default_factory=Future, init=False, repr=False)
  _set: bool = field(default=False, init=False, repr=False)

  def is_set(self):
    return self._set

  def set(self):
    self.toggle(True)

  def unset(self):
    self.toggle(False)

  def toggle(self, value: bool, /):
    if self._set != value:
      self._future.set_result(None)
      self._future = Future[None]()
      self._set = value

  async def wait(self):
    await asyncio.shield(self._future)
    return self._set

  async def wait_set(self):
    if not self._set:
      await asyncio.shield(self._future)

  async def wait_unset(self):
    if self._set:
      await asyncio.shield(self._future)


__all__ = [
  'Latch',
]
