import asyncio
import contextlib
import sys
import traceback
from asyncio import Event, Future, Task
from dataclasses import dataclass, field
from traceback import FrameSummary
from types import TracebackType
from typing import Any, AsyncGenerator, Coroutine, Literal, Optional, Self

from .race import race


class InvalidPoolStatusError(RuntimeError):
  pass

class LazyTaskProtocolError(RuntimeError):
  pass


@dataclass(slots=True)
class HierarchyNode:
  name: list[str] | str
  children: list[Self | list[str]] = field(default_factory=list)

  def format(self, *, prefix: str = str()):
    name = self.name if isinstance(self.name, list) else [self.name]

    return ("\n" + prefix).join(name) + str().join([
      "\n" + prefix
        + ("└── " if (last := (index == (len(self.children) - 1))) else "├── ")
        + (child.format(prefix=(prefix + ("    " if last else "│   "))) if isinstance(child, HierarchyNode) else ("\n" + prefix + ("    " if last else "│   ")).join(child))
        for index, child in enumerate(self.children)
    ])


@dataclass(slots=True)
class PoolTaskInfo:
  call_tb: Optional[TracebackType]
  depth: int
  frame: Optional[FrameSummary]
  pool: 'Optional[Pool]' = None

class Pool:
  """
  An object used to manage tasks created in a common context.
  """

  _pools_by_task = dict[Task[None], Self]()

  def __init__(self, name: Optional[str] = None):
    self._closing_depth: Optional[int] = None
    self._direct_pool: Optional[Self] = None
    self._name = name
    self._running = False
    self._owning_task: Optional[Task[Any]] = None
    self._parent_pool: Optional[Self] = None
    self._task_event = Event()
    self._tasks = dict[Task[None], PoolTaskInfo]()

  def _prepare_format(self, path_filter: list[Self]):
    node = HierarchyNode(self._name or "<Untitled pool>")

    for task, task_info in self._tasks.items():
      if path_filter and (task_info.pool is not path_filter[0]):
        continue

      task_node = HierarchyNode([
        f"{task.get_name()}" + (f" (depth={task_info.depth})" if task_info.depth != 0 else str()),
        *([f"Source: {frame.name}() in {frame.filename}" + (f":{frame.lineno}" if frame.lineno is not None else str())] if (frame := task_info.frame) else [])
      ])

      node.children.append(task_node)

      if task_info.pool:
        task_node.children.append(task_info.pool._prepare_format(path_filter[1:])) # type: ignore

    if self._direct_pool:
      node.children.append(self._direct_pool._prepare_format(path_filter[1:]))

    return node

  def format(self, *, ancestors: Literal['all', 'none', 'path'] = 'path'):
    pool_path = [self]
    target_pool = self

    if ancestors != 'none':
      while (parent_pool := target_pool._parent_pool):
        pool_path.append(parent_pool)
        target_pool = parent_pool

    root_node = target_pool._prepare_format(pool_path[1::-1] if ancestors == 'path' else [])

    if (ancestors != 'none') and target_pool._owning_task:
      root_node = HierarchyNode(target_pool._owning_task.get_name(), [root_node])

    return root_node.format()


  def __len__(self):
    return len(self._tasks)

  def __repr__(self):
    return f"{self.__class__.__name__}" + (f"(name={self._name!r})" if self._name else "()")

  def _add(self, task: Task[None], /, *, _frame_skip: int = 0, depth: int = 0):
    """
    Add a new task to the pool.

    Parameters
      depth: The depth of the task.
      task: The task to add.
    """

    if not self._running:
      raise InvalidPoolStatusError("Pool not open")

    self._tasks[task] = PoolTaskInfo(
      call_tb=slice_tb_start(create_tb(_frame_skip), 9),
      depth=depth,
      frame=traceback.extract_stack(limit=(2 + _frame_skip))[0]
    )

    # slice_tb_start(self._tasks[task].call_trace, 0)
    # traceback.print_tb(self._tasks[task].call_trace)
    # print()
    # print()

    self.__class__._pools_by_task[task] = self

    # Wake up the wait() loop if necessary
    self._task_event.set()

  def _close(self):
    """
    Cancel all tasks currently in the pool.

    Calling this function multiple times will increment the cancellation counter of tasks already in the pool, and cancel newly-added tasks.
    """

    if self._tasks:
      self._closing_depth = self._max_depth()

      for task, task_info in self._tasks.items():
        if task_info.depth >= self._closing_depth:
          task.cancel()
    else:
      self._closing_depth = 0

      # Wake up wait() and have it return
      self._task_event.set()

  def run(self, *, forever: bool = False):
    """
    Run the pool.

    Cancelling this call cancels all tasks in the pool.
    """

    if self._running:
      raise InvalidPoolStatusError("Pool already open")

    self._running = True
    return self._wait(forever=forever)

  def _max_depth(self):
    return max(task_info.depth for task_info in self._tasks.values())

  async def _wait(self, *, forever: bool):
    exceptions = list[BaseException]()

    # call_trace = list(self._tasks.values())[1].call_trace

    while True:
      self._task_event.clear()

      try:
        await race(
          self._task_event.wait(),
          *([asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)] if self._tasks else list())
        )
      except asyncio.CancelledError:
        # Reached when the call to wait() is cancelled
        self._close()

      for task in list(self._tasks.keys()):
        if task.done():
          try:
            exc = task.exception()
          except asyncio.CancelledError:
            pass
          else:
            if exc:
              task_info = self._tasks[task]
              join_tbs(task_info.call_tb, exc.__traceback__)
              exceptions.append(exc.with_traceback(task_info.call_tb))

          del self._tasks[task]
          del self.__class__._pools_by_task[task]

      if (exceptions and (self._closing_depth is None)) or (self._tasks and (self._closing_depth is not None) and (self._max_depth() < self._closing_depth)):
        self._close()

      if (not self._tasks) and ((not forever) or (self._closing_depth is not None)):
        break

    self._running = False

    # if current_pool:
    #   current_pool._tasks[current_task].pool = None

    if len(exceptions) >= 2:
      raise BaseExceptionGroup("Pool", exceptions)
    if exceptions:
      raise exceptions[0]

  def spawn(
    self,
    coro: Coroutine[Any, Any, None],
    /, *,
    _frame_skip: int = 0,
    critical: bool = False,
    depth: int = 0,
    name: Optional[str] = None,
  ):
    """
    Create a task from the provided coroutine and add it to the pool.

    Parameters:
      coro: The coroutine from which to create a task.
      critical: Whether to close the pool when this task finishes.
      depth: The task's depth. Tasks with a lower depth will only be cancelled once all tasks with a higher depth have finished.
      name: The task's name.
    """

    if not self._running:
      raise InvalidPoolStatusError("Pool not open")

    task = asyncio.create_task(coro, name=name)
    self._add(task, _frame_skip=(_frame_skip + 1), depth=depth)

    if critical:
      def callback(task: Task[None]):
        try:
          task.result()
        except:
          pass
        else:
          if self._closing_depth is None:
            self._close()

      task.add_done_callback(callback)

  async def spawn_lazy(
    self,
    coro: AsyncGenerator[None, None],
    /, *,
    depth: int = 0,
    name: Optional[str] = None
  ):
    """
    Create a two-phase task and return once the first phase is over.

    If an exception occurs or if the pool is cancelled during the first phase, this method never returns. Cancelling this method has no effect.

    Parameters
      coro: An asynchronous generator that yields exactly once between the first and second phase, from which to create the task.
      depth: The task's depth.
      name: The task's name.

    Raises
      LazyTaskProtocolError: If the coroutine does not yield exactly once.
    """

    ready_event = Event()

    async def wrapper_coro():
      coro_iter = aiter(coro)

      try:
        await anext(coro_iter)
      except StopAsyncIteration:
        raise LazyTaskProtocolError("Coroutine did not yield")

      ready_event.set()

      try:
        await anext(coro_iter)
      except StopAsyncIteration:
        pass
      else:
        raise LazyTaskProtocolError("Coroutine did not stop after first yield")

    self.spawn(wrapper_coro(), _frame_skip=1, depth=depth)
    await ready_event.wait()

  def spawn_handled(
    self,
    coro: Coroutine[Any, Any, None],
    /, *,
    depth: int = 0,
    name: Optional[str] = None
  ):
    """
    Create a task and return a handle to it.

    Parameters
      coro: The coroutine from which to create a task.
      depth: The task's depth.
      name: The task's name.

    Returns
      A `TaskHandle` object that can be used to interrupt the task.
    """

    if not self._running:
      raise InvalidPoolStatusError("Pool not open")

    inner_task = asyncio.create_task(coro)
    handle = TaskHandle(inner_task)

    async def outer_func():
      cancelled = False

      while True:
        try:
          await asyncio.shield(inner_task)
        except asyncio.CancelledError:
          if inner_task.cancelled():
            raise

          if (not handle.interrupted()) or cancelled:
            inner_task.cancel()

          cancelled = True

    self.spawn(outer_func(), name=name, depth=depth) # TODO: Check frames

    return handle

  @classmethod
  def current(cls):
    """
    Get the current pool.

    Returns
      A `Pool` object, or `None` if there is no current task or if the current task is not running in a pool.
    """

    current_task = asyncio.current_task()
    return current_task and cls._pools_by_task.get(current_task)

  @classmethod
  @contextlib.asynccontextmanager
  async def open(cls, name: Optional[str] = None, *, forever: bool = False):
    """
    Create an asynchronous context with a dedicated pool.

    The context will not return until all tasks in the pool have finished.

    Parameters
      forever: Whether the pool should stay open once all tasks have finished.
      name: The pool's name.
    """

    current_task = asyncio.current_task()
    assert current_task

    pool = cls(name)
    pool._owning_task = current_task
    pool._parent_pool = cls.current()

    current_task_future = Future[None]()
    run_task = asyncio.create_task(pool.run(forever=forever))

    async def current_task_handler():
      while True:
        try:
          await asyncio.shield(current_task_future)
        except asyncio.CancelledError:
          # If the task was cancelled from the outside
          if current_task_future.done():
            if pool._closing_depth is None:
              pool._close()

            raise

          # Otherwise, the pool is being closed
          current_task.cancel()
        else:
          if current_task_future.done():
            break

    pool.spawn(current_task_handler(), _frame_skip=2, name='<Asynchronous context manager>')

    current_task_old_pool = cls._pools_by_task.get(current_task)
    cls._pools_by_task[current_task] = pool

    if current_task_old_pool:
      if current_task is not current_task_old_pool._owning_task:
        current_task_old_pool._tasks[current_task].pool = pool
      else:
        assert not current_task_old_pool._direct_pool
        current_task_old_pool._direct_pool = pool

    try:
      yield pool
    except BaseException as e:
      current_task_future.set_exception(e)
    else:
      current_task_future.set_result(None)

    if current_task_old_pool is not None:
      cls._pools_by_task[current_task] = current_task_old_pool
    else:
      del cls._pools_by_task[current_task]

    try:
      await run_task
    except Exception as e:
      raise e.with_traceback(slice_tb_start(e.__traceback__, 2))
    finally:
      if current_task_old_pool:
        if current_task is not current_task_old_pool._owning_task:
          current_task_old_pool._tasks[current_task].pool = None
        else:
          current_task_old_pool._direct_pool = None


@dataclass(frozen=True, slots=True)
class TaskHandle:
  """
  An object used to control a task running in a pool.
  """

  task: Task

  def interrupt(self):
    """
    Interrupt the task, that is, cancel it if it is not already cancelled.
    """

    if not self.interrupted():
      self.task.cancel()

  def interrupted(self):
    """
    Get whether the task has been interrupted.
    """

    return self.task.cancelling() > 0


# Utility functions

def create_tb(start_depth: int = 0):
  tb: Optional[TracebackType] = None
  depth = (start_depth + 2)

  while True:
    try:
      frame = sys._getframe(depth)
      depth += 1
    except ValueError:
      break

    tb = TracebackType(tb, frame, frame.f_lasti, frame.f_lineno)

  return tb


def join_tbs(start: Optional[TracebackType], end: Optional[TracebackType]):
  if not start:
    return end

  current_tb = start

  while (next_tb := current_tb.tb_next):
    current_tb = next_tb

  current_tb.tb_next = end

def slice_tb_start(tb: Optional[TracebackType], size: int):
  current_tb = tb

  for _ in range(size):
    if not current_tb:
      return None

    current_tb = current_tb.tb_next

  return current_tb

def slice_tb_end(tb: TracebackType, size: int):
  tbs = []

  current_tb = tb

  while current_tb:
    tbs.append(current_tb)
    current_tb = current_tb.tb_next

  if size > 0:
    tbs[-size - 1].tb_next = None


__all__ = [
  'InvalidPoolStatusError',
  'LazyTaskProtocolError',
  'Pool',
  'TaskHandle'
]
