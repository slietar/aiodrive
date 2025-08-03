import asyncio
import contextlib
from asyncio import Task
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Optional


@dataclass(slots=True)
class BackgroundExecutor:
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
