from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..modules.button import Button


@dataclass(slots=True)
class OrderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _close_index: Optional[int] = field(default=None, init=False, repr=False)
  _current_index: int = field(default=0, init=False, repr=False)
  _items: dict[int, T] = field(default_factory=dict, init=False, repr=False)
  _reserved_count: int = field(default=0, init=False, repr=False)

  async def __aiter__(self):
    while self._current_index != self._close_index:
      if self._current_index in self._items:
        item = self._items.pop(self._current_index)
        self._current_index += 1
        yield item

      await self._button

  async def __len__(self):
    return len(self._items)

  def close(self):
    assert self._close_index is None
    self._close_index = self._reserved_count

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
  _close_index: Optional[int] = field(default=None, init=False, repr=False)
  _current_index: int = field(default=0, init=False, repr=False)
  _items: deque[T] = field(default_factory=deque, init=False, repr=False)
  _reserved_count: int = field(default=0, init=False, repr=False)

  async def __aiter__(self):
    while self._current_index != self._close_index:
      if not self._items:
        await self._button

      self._current_index += 1
      yield self._items.popleft()

  async def __len__(self):
    return len(self._items)

  def close(self):
    assert self._close_index is None
    self._close_index = self._reserved_count

  def reserve(self):
    assert self._close_index is None
    self._reserved_count += 1

    def put(item: T):
      self._items.append(item)
      self._button.press()

    return put


type QueueType = OrderedQueue | UnorderedQueue
