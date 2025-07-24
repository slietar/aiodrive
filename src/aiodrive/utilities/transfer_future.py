from asyncio import Future
from collections.abc import Callable


def transfer_future[T, S](source: Future[T], destination: Future[S], *, transform: Callable[[T], S] = (lambda x: x)):
  assert source.done()

  if source.cancelled():
    destination.cancel()
  elif exc := source.exception():
    destination.set_exception(exc)
  else:
    destination.set_result(transform(source.result()))
