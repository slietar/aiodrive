from asyncio import Event, Future, Lock
import asyncio
from dataclasses import dataclass, field
from typing import Generic, TypeVar


@dataclass(slots=True)
class Button:
  _event: Event = field(default_factory=Event)

  async def wait(self):
    await self._event.wait()

  def set(self):
    self._event.set()
    self._event.clear()


T_cv = TypeVar('T_cv', contravariant=True)

@dataclass(slots=True)
class Cargo(Generic[T_cv]):
  _future: Future[T_cv] = field(default_factory=Future)

  def __await__(self):
    return asyncio.shield(self._future).__await__()

  def set(self, result: T_cv, /):
    self._future.set_result(result)
    self._future = Future()


@dataclass(slots=True)
class Channel[S]:
  _cargo: Cargo[S] = field(default_factory=Cargo)
  _button: Button = field(default_factory=Button)
  _lock: Lock = field(default_factory=Lock)
  _received_count: int = 0
  _receiver_count: int = 0

  async def receive(self):
    self._receiver_count += 1
    item = await self._cargo
    self._received_count += 1

    if self._received_count == self._receiver_count:
      self._received_count = 0
      self._receiver_count = 0
      self._button.set()

    return item

  # Can only send one item at a time
  async def send(self, item: S, /):
    async with self._lock:
      self._cargo.set(item)
      await self._button.wait()
