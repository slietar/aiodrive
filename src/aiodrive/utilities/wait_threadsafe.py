from asyncio import Future, Task
import asyncio


async def wait_on_other_loop[T](task: Task[T]):
  # TODO: What happens if the loop is closed?

  future = Future[T]()

  def callback(task: Task[T]):
    if task.cancelled():
      task.cancel()
    elif (exception := task.exception()) is not None:
      task.set_exception(exception)
    else:
      task.set_result(task.result())

  task.add_done_callback(lambda task: asyncio.get_running_loop().call_soon_threadsafe(callback, task))

  try:
    return await future
  finally:
    task.remove_done_callback(callback)
