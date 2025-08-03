from collections import deque
from dataclasses import dataclass, field

from .button import Button


@dataclass(slots=True)
class OrderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _current_index: int = field(default=0, init=False, repr=False)
  _items: dict[int, T] = field(default_factory=dict, init=False, repr=False)

  def empty(self):
    return not self._items

  async def get(self):
    while True:
      if self._current_index in self._items:
        item = self._items.pop(self._current_index)
        self._current_index += 1
        return item

      await self._button

  def put(self, index: int, item: T):
    if index < self._current_index:
      raise ValueError(f"Cannot put item at index {index} as it is less than the current index {self._current_index}.")

    if index in self._items:
      raise ValueError(f"Item at index {index} already exists in the queue.")

    self._items[index] = item

    if index == self._current_index:
      self._button()


@dataclass(slots=True)
class UnorderedQueue[T]:
  _button: Button = field(default_factory=Button, init=False, repr=False)
  _items: deque[T] = field(default_factory=deque, init=False, repr=False)

  def empty(self):
    return not self._items

  async def get(self):
    while not self._items:
      await self._button

    return self._items.popleft()

  def put(self, index: int, item: T):
    self._items.append(item)
    self._button()
