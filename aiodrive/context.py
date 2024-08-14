from typing import Any, Awaitable, Callable


def aexit_handler(func: Callable[[Any, bool], Awaitable[None]], /):
  """
  Create an asynchronous exit handler for a function or method while handling any exception raised in the context block.

  Any exception raised in the context is raised again after the handler finishes and it is not possible to intercept that exception. If an exception is raised both in the context and the exit handler, a `BaseExceptionGroup` with both exceptions is raised.

  Parameters
    func: A function or method which takes a single argument, a boolean indicating whether an exception was raised in the context.

  Returns
    A new asynchronous exit handler.
  """

  async def new_func(self, exc_type, exc_value, traceback):
    exceptions = list[BaseException]()

    if exc_type:
      exceptions.append(exc_value)

    try:
      await func(self, (exc_type is not None))
    except BaseException as e:
      exceptions.append(e)

    if len(exceptions) > 1:
      raise BaseExceptionGroup("Asynchronous exit handler", exceptions) from None
    elif exceptions:
      raise exceptions[0] from None

  return new_func


__all__ = [
  'aexit_handler'
]
