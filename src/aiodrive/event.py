from asyncio import Event


class LatchEvent:
  """
  An equivalent to `asyncio.Event` that can watched for both set and unset events.

  TODO: Clarify what happens when calling set() and unset() one just after the other.
  """

  def __init__(self):
    self._set_event = Event()
    self._unset_event = Event()

  def is_set(self):
    """
    Return `True` if the event is set.
    """

    return self._set_event.is_set()

  def set(self):
    """
    Set the event.
    """

    self._set_event.set()
    self._unset_event.clear()

  def unset(self):
    """
    Return `True` if the event is unset.

    This function is analoguous to `asyncio.Event.clear()`.
    """

    self._set_event.clear()
    self._unset_event.set()

  def toggle(self, value: bool, /):
    """
    Set or unset the event depending on the provided boolean.

    Parameters
      value: Whether to set the event.
    """

    if value:
      self.set()
    else:
      self.unset()

  async def wait_set(self):
    """
    Wait for the event to be set.

    Returns immediately if the event is already set.
    """

    await self._set_event.wait()

  async def wait_unset(self):
    """
    Wait for the event to be unset.

    Returns immediately if the event is already unset.
    """

    await self._unset_event.wait()


__all__ = [
  'LatchEvent'
]
