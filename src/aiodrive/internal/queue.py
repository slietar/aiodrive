from collections import deque
from dataclasses import dataclass, field

from ..modules.button import Button


@dataclass(slots=True)
class OrderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _closed: bool = field(default=False, init=False, repr=False)
  _current_index: int = field(default=0, init=False, repr=False)
  _items: dict[int, T] = field(default_factory=dict, init=False, repr=False)
  _reserved_count: int = field(default=0, init=False, repr=False)

  async def __aiter__(self):
    while (not self._closed) or (self._current_index < self._reserved_count):
      if self._current_index not in self._items:
        await self._button
        continue

      item = self._items.pop(self._current_index)
      self._current_index += 1
      yield item

  async def __len__(self):
    return len(self._items)

  def close(self):
    assert not self._closed
    self._closed = True

    if self._current_index == self._reserved_count:
      self._button.press()

  def reserve(self):
    assert not self._closed

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
  _closed: bool = field(default=False, init=False, repr=False)
  _items: deque[T] = field(default_factory=deque, init=False, repr=False)
  _reserved_count: int = field(default=0, init=False, repr=False)

  async def __aiter__(self):
    while (not self._closed) or self._items:
      if not self._items:
        await self._button
        continue

      yield self._items.popleft()

  async def __len__(self):
    return len(self._items)

  def close(self):
    assert not self._closed
    self._closed = True

  def reserve(self):
    assert not self._closed
    self._reserved_count += 1

    def put(item: T):
      self._items.append(item)
      self._button.press()

    return put


type QueueType = OrderedQueue | UnorderedQueue
