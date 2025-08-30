import asyncio
import contextlib
from asyncio import Task
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Optional


# TODO: Rename ThreadTaskGroup with a .spawn() method; and add a second class
# "BackgroundExecutor" with an optional global async context manager and a
# mandadatory context manager for creating tasks


@dataclass(slots=True)
class BackgroundExecutor:
  """
  An executor that runs background tasks on a shared separate thread.

  Use this class if there is the main thread might become blocked while some
  essential tasks, such as logging, need to continue running in the background.

  The executor is started by entering the associated context manager, which
  causes the thread to start. When the context manager exits, the executor
  stops: remaining tasks are cancelled, awaited, and the thread is then joined.
  A task that finishes before the context manager exits does not cause any
  particular action. When a task raises an exception, the executor stops in a
  similar manner; remaining tasks of the executor, as well as the current task,
  are cancelled, awaited, and the thread is then joined. Any exception raised by
  tasks is propagated to the context manager exit.

  After it stops, the executor may be re-started by entering the context manager
  again. Tasks may not be spawned while the executor is not running or while it
  is starting or stopping. Spawning tasks is not thread-safe.
  """

  loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_event_loop, init=False)
  next_task_id: int = field(default=0, init=False)
  ready: Event = field(default_factory=Event, init=False)
  tasks: dict[int, Task] = field(default_factory=dict, init=False)
  thread: Optional[Thread] = field(default=None, init=False)

  def add_task(self, task_id: int, coro: Awaitable[None]):
    self.tasks[task_id] = asyncio.ensure_future(coro)

  def thread_run(self):
    self.loop = asyncio.new_event_loop()
    self.loop.run_forever()
    self.ready.set()

  @contextlib.asynccontextmanager
  async def run(self, target: Callable[[], Awaitable[None]], /):
    task_id = self.next_task_id

    self.loop.call_soon_threadsafe(self.add_task, task_id, target())
    self.next_task_id += 1

    # TODO: Wait for the task to start

    try:
      yield
    finally:
      task = self.tasks.pop(task_id)
      task.cancel()

      # TODO: Wait for the task to finish

  async def __aenter__(self):
    assert self.thread is None

    self.thread = Thread(target=self.thread_run)
    self.thread.start()

    # This is blocking but negligible
    self.ready.wait()

  async def __aexit__(self, exc_type, exc_value, traceback):  # noqa: ANN001
    assert self.thread is not None

    self.loop.call_soon_threadsafe(self.loop.close)
    self.thread.join()
