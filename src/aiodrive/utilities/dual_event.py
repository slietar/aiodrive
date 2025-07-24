from asyncio import Event


class DualEvent:
  def __init__(self):
    self._set_event = Event()
    self._unset_event = Event()

  def is_set(self):
    return self._set_event.is_set()

  def set(self):
    self._set_event.set()
    self._unset_event.clear()

  def unset(self):
    self._set_event.clear()
    self._unset_event.set()

  def toggle(self, value: bool, /):
    if value:
      self.set()
    else:
      self.unset()

  async def wait_set(self):
    await self._set_event.wait()

  async def wait_unset(self):
    await self._unset_event.wait()
