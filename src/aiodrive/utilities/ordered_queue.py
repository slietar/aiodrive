from collections import deque
from dataclasses import dataclass, field

from .button import Button


@dataclass(slots=True)
class OrderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _current_index: int = field(default=0, init=False, repr=False)
  _items: dict[int, T] = field(default_factory=dict, init=False, repr=False)
  _reserved_count: int = field(default=0, init=False, repr=False)

  async def __aiter__(self):
    while True:
      yield await self.get()

  async def __len__(self):
    return len(self._items)

  async def get(self):
    while True:
      if self._current_index in self._items:
        item = self._items.pop(self._current_index)
        self._current_index += 1
        return item

      await self._button

  def reserve(self):
    index = self._reserved_count
    self._reserved_count += 1

    def put(item: T):
      self._items[index] = item

      if index == self._current_index:
        self._button.press()

    return put


@dataclass(slots=True)
class UnorderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _items: deque[T] = field(default_factory=deque, init=False, repr=False)

  async def __aiter__(self):
    while True:
      yield await self.get()

  async def __len__(self):
    return len(self._items)

  async def get(self):
    while not self._items:
      await self._button

    return self._items.popleft()

  def reserve(self):
    def put(item: T):
      self._items.append(item)
      self._button.press()

    return put


type QueueType = OrderedQueue | UnorderedQueue
