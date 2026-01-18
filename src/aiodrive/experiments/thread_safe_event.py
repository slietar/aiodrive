from dataclasses import dataclass, field

from ..modules.thread_safe_state import ThreadsafeState


# Problem: wait() will not return if the event is quickly set and unset by another thread


@dataclass(slots=True)
class ThreadsafeEvent:
  _state: ThreadsafeState = field(
    default_factory=(lambda: ThreadsafeState(False)),
    init=False,
    repr=False,
  )

  def clear(self):
    self._state.set_value(False)

  def is_set(self):
    return self._state.value

  def set(self):
    self._state.set_value(True)

  def unset(self):
    self._state.set_value(False)

  async def wait_set(self):
    await self._state.wait_until(lambda value: value)

  async def wait_unset(self):
    await self._state.wait_until(lambda value: not value)


__all__ = [
  'ThreadsafeEvent',
]
