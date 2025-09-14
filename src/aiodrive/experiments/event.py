from dataclasses import dataclass, field

from ..modules.thread_safe_button import ThreadsafeButton


@dataclass(slots=True)
class ThreadsafeEvent:
  _active: bool = field(default=False, init=False, repr=False)
  _button: ThreadsafeButton = field(default_factory=ThreadsafeButton, init=False, repr=False)

  def clear(self):
    self._active = False

  def is_set(self):
    return self._active

  def set(self):
    self._active = True
    self._button.press()

  def unset(self):
    self._active = False

  async def wait(self):
    while not self._active:
      await self._button


__all__ = [
  'ThreadsafeEvent',
]
