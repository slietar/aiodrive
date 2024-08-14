import asyncio
import contextlib
import logging
import sys
import traceback
from asyncio import Event, Future, Task
from dataclasses import dataclass, field
from traceback import FrameSummary, TracebackException
from types import TracebackType
from typing import Any, AsyncGenerator, Coroutine, Literal, Optional, Self

from .race import race


class InvalidPoolStatusError(RuntimeError):
  pass

class LazyPoolTaskProtocolError(RuntimeError):
  pass

class TraceException(BaseException):
  pass


@dataclass(slots=True)
class HierarchyNode:
  name: list[str] | str
  children: list[Self | list[str]] = field(default_factory=list)

  def format(self, *, prefix: str = ''):
    name = self.name if isinstance(self.name, list) else [self.name]

    return ('\n' + prefix).join(name) + ''.join([
      '\n' + prefix
        + ('└── ' if (last := (index == (len(self.children) - 1))) else '├── ')
        + (child.format(prefix=(prefix + ('    ' if last else '│   '))) if isinstance(child, HierarchyNode) else ('\n' + prefix + ('    ' if last else '│   ')).join(child))
        for index, child in enumerate(self.children)
    ])


@dataclass(slots=True)
class PoolTaskInfo:
  call_tb: Optional[TracebackType]
  depth: int
  frame: Optional[FrameSummary]
  pool: 'Optional[Pool]' = None

@dataclass(frozen=True, slots=True)
class PoolTaskSpec:
  coro: Coroutine[Any, Any, None]
  name: Optional[str]
  info: PoolTaskInfo

type PoolStatus = Literal['done', 'idle', 'running']

@dataclass(frozen=True, slots=True)
class PoolTaskHandle:
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


class Pool:
  """
  An object used to manage tasks created in a common context.
  """

  # Pool owning each task, as seen by the user.
  _pools_by_task = dict[Task[None], Self]()

  def __init__(self, name: Optional[str] = None):
    self._cancellation_depth: Optional[int] = None
    self._direct_pool: Optional[Self] = None
    self._logger = logging.getLogger('aiotoolbox')
    self._loop_wake_up_event = Event()
    self._name = name
    self._owning_task: Optional[Task[Any]] = None
    self._parent_pool: Optional[Self] = None
    self._planned_tasks = list[PoolTaskSpec]()
    self._status: PoolStatus = 'idle'
    self._tasks = dict[Task[None], PoolTaskInfo]()

  def _prepare_format(self, path_filter: list[Self]):
    node = HierarchyNode((self._name or '<Untitled pool>') + f' (cancellation_depth={self._cancellation_depth if self._cancellation_depth is not None else '<none>'})')

    for task, task_info in self._tasks.items():
      if path_filter and (task_info.pool is not path_filter[0]):
        continue

      task_node = HierarchyNode([
        # TODO: Add task cancellation count
        f'{task.get_name()} (depth={task_info.depth}, cancellation_count={task.cancelling()})',
        *([f'Source: {frame.name}{'()' if frame.name[0] != '<' else ''} in {frame.filename}' + f':{frame.lineno}' if frame.lineno is not None else ''] if (frame := task_info.frame) else [])
      ])

      node.children.append(task_node)

    #   if task_info.pool:
    #     task_node.children.append(task_info.pool._prepare_format(path_filter[1:])) # type: ignore

    # if self._direct_pool:
    #   node.children.append(self._direct_pool._prepare_format(path_filter[1:]))

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
    """
    Get the number of tasks in the pool.
    """

    return len(self._tasks)

  def __repr__(self):
    return f"{self.__class__.__name__}" + (f"(name={self._name!r})" if self._name else "()")

  def _close(self):
    """
    Cancel all tasks currently in the pool.

    Calling this function multiple times will increment the cancellation counter of tasks already in the pool, and cancel newly-added tasks.
    """

    self._cancellation_depth = self._max_task_depth()
    self._logger.debug(f'Cancelling tasks with depth >= {self._cancellation_depth}')

    for task, task_info in self._tasks.items():
      if task_info.depth >= self._cancellation_depth:
        task.cancel()
        self._logger.debug(f'Cancelling task {task.get_name()} with depth {task_info.depth} and new cancellation count {task.cancelling()}')

    if not self._tasks:
      # Wake up _wait() and have it return
      self._loop_wake_up_event.set()

  def _max_task_depth(self):
    return max((0, *(task_info.depth for task_info in self._tasks.values())))

  def _spawn_from_spec(self, spec: PoolTaskSpec, /):
    assert self._status == 'running'

    task = asyncio.create_task(spec.coro, name=spec.name)
    self._logger.debug(f'Spawning task {task.get_name()} with depth {spec.info.depth}')

    self._tasks[task] = spec.info
    self.__class__._pools_by_task[task] = self

    # Wake up the wait() loop to start awaiting this task
    self._loop_wake_up_event.set()

  async def _wait(self, *, forever: bool):
    exceptions = list[BaseException]()

    while self._tasks or (
      forever and
      (self._cancellation_depth is None)
    ):
      try:
        await race(
          # Completed when a new task is added, necessary for this method to start awaiting that task
          self._loop_wake_up_event.wait(),

          # Completed when an existing task completes
          *([asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)] if self._tasks else [])
        )
      except asyncio.CancelledError:
        # Reached when the call to _wait() is cancelled
        self._close()

      self._loop_wake_up_event.clear()

      # Iterate over all tasks to remove them if they are done
      for task in list(self._tasks.keys()):
        if task.done():
          try:
            exc = task.exception()
          except asyncio.CancelledError:
            # Reached when the pool is being cancelled
            pass
          else:
            if exc:
              task_info = self._tasks[task]
              trace_exc = TraceException().with_traceback(task_info.call_tb)

              # Find first exception in causality chain
              current_exc = exc

              while current_exc.__cause__ is not None:
                current_exc = current_exc.__cause__

              current_exc.__cause__ = trace_exc

              exceptions.append(exc)

          self._logger.debug(f'Collected task {task.get_name()}')

          del self._tasks[task]
          del self.__class__._pools_by_task[task]

      # Close the pool
      #   - if a task failed and the pool is not closing, as to not cancel tasks again;
      #   - or if the pool is being closed but the cancellation depth is too high for remaining tasks.
      if (
        exceptions and
        (self._cancellation_depth is None)
      ) or (
        self._tasks and
        (self._cancellation_depth is not None) and
        (self._max_task_depth() < self._cancellation_depth)
      ):
        self._close()

    self._logger.debug('Closing pool')
    self._status = 'done'

    if len(exceptions) >= 2:
      raise BaseExceptionGroup('Pool', exceptions)
    if exceptions:
      raise exceptions[0]

  def run(self, *, forever: bool = False):
    """
    Run the pool.

    Cancelling this call cancels all tasks in the pool.

    Parameters
      forever: Whether to keep the pool running once all tasks have finished.
    """

    if self._status != 'idle':
      raise InvalidPoolStatusError('Attempting to run a pool that is not idle')

    self._owning_task = asyncio.current_task()
    self._parent_pool = self.current()
    self._status = 'running'

    for spec in self._planned_tasks:
      self._spawn_from_spec(spec)

    self._planned_tasks.clear()

    return self._wait(forever=forever)

  def spawn(
    self,
    coro: Coroutine[Any, Any, None],
    /, *,
    _frame_skip: int = 0,
    depth: int = 0,
    name: Optional[str] = None,
  ):
    """
    Create a task from the provided coroutine and add it to the pool.

    Parameters:
      coro: The coroutine from which to create a task.
      depth: The task's depth. Tasks with a lower depth will only be cancelled once all tasks with a higher depth have finished.
      name: The task's name.
    """

    # traceback.print_tb(create_tb(0))

    info = PoolTaskInfo(
      call_tb=slice_tb_start(create_tb(_frame_skip), 0),
      depth=depth,
      frame=traceback.extract_stack(limit=(_frame_skip + 2))[0]
    )

    spec = PoolTaskSpec(coro, name, info)

    match self._status:
      case 'done':
        raise InvalidPoolStatusError
      case 'idle':
        self._planned_tasks.append(spec)
        self._logger.debug(f'Planning {f'task {name}' if name is not None else 'anonymous task'} with depth {depth}')
      case 'running':
        self._spawn_from_spec(spec)

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
        raise LazyPoolTaskProtocolError('Coroutine did not yield')

      ready_event.set()

      try:
        await anext(coro_iter)
      except StopAsyncIteration:
        pass
      else:
        raise LazyPoolTaskProtocolError('Coroutine did not stop after first yield')

    self.spawn(wrapper_coro(), _frame_skip=1, depth=depth, name=name)
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
      A `PoolTaskHandle` object that can be used to interrupt the task.
    """

    if not self._status != 'running':
      raise InvalidPoolStatusError

    inner_task = asyncio.create_task(coro)
    handle = PoolTaskHandle(inner_task)

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

    self.spawn(outer_func(), depth=depth, name=name) # TODO: Check frames

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
            if pool._cancellation_depth is None:
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


# Utility functions

def create_tb(start_depth: int = 0):
  tb: Optional[TracebackType] = None
  depth = start_depth + 2

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


__all__ = [
  'InvalidPoolStatusError',
  'LazyPoolTaskProtocolError',
  'Pool',
  'PoolTaskHandle'
]
