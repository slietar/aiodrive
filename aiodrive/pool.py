import asyncio
import contextlib
import logging
from pathlib import Path
import sys
from asyncio import Event, Future, Task
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, AsyncGenerator, Coroutine, Iterable, Literal, Optional, Self, cast

from .ansi import EscapeSeq
from .race import race


# TODO: Warn when a task should have raised a asyncio.CancelledError but did not


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
  pool: 'Optional[Pool]' = None
  skip_tb_trace: bool = False

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

  # Maps which pool a task belongs to
  _pools_by_task_regular = dict[Task[None], Self]()

  # Same but for the task of pools opened with contexts
  _pools_by_task_context = dict[Task[None], Self]()

  def __init__(self, name: Optional[str] = None):
    self._cancellation_depth: Optional[int] = None
    self._context_task: Optional[Task[None]] = None # The fake task used to control the context, if any
    self._logger = logging.getLogger('aiodrive')
    self._loop_wake_up_event = Event()
    self._name = name
    self._owning_task: Optional[Task[None]] = None # In contexts, corresponds to the root task
    self._parent_pool: Optional[Self] = None
    self._planned_tasks = list[PoolTaskSpec]()
    self._status: PoolStatus = 'idle'
    self._tasks = dict[Task[None], PoolTaskInfo]()

  def _prepare_format(self, path_filter: list[Self], highlight: Self):
    # An empty path_filter means no filtering

    # TODO: Add pool status and planned tasks

    node = HierarchyNode((EscapeSeq.underline if self == highlight else '') + (self._name or '<Untitled pool>') + f'{EscapeSeq.reset} {EscapeSeq.bright_black}(cancellation_depth={self._cancellation_depth if self._cancellation_depth is not None else '<none>'}){EscapeSeq.reset}')

    for task, task_info in self._tasks.items():
      if path_filter and (task_info.pool is not path_filter[0]):
        continue

      if task_info.call_tb:
        tb = last(walk_tb(task_info.call_tb))

        frame_code = tb.tb_frame.f_code
        trace_path_str = frame_code.co_filename
        trace_funcname = frame_code.co_name
        trace_lineno = tb.tb_lineno

        if trace_path_str[0] != '<':
          trace_path = Path(trace_path_str)

          try:
            trace_path_rel = trace_path.relative_to(Path.cwd())
          except ValueError:
            trace_location = f'{trace_path_str}:{trace_lineno}'
          else:
            trace_location = f'./{trace_path_rel}:{trace_lineno}'
        else:
          trace_location = trace_path_str

        trace_str = f'Source: {trace_funcname}{'()' if trace_funcname[0] != '<' else ''} {EscapeSeq.bright_black}in {trace_location}{EscapeSeq.reset}'
      else:
        trace_str = None

      task_node = HierarchyNode([
        f'{task.get_name()} {EscapeSeq.bright_black}(depth={task_info.depth}, cancellation_count={task.cancelling()}){EscapeSeq.reset}',
        *([trace_str] if trace_str is not None else [])
      ])

      node.children.append(task_node)

      if task_info.pool is not None:
        task_node.children.append(task_info.pool._prepare_format(path_filter[1:], highlight)) # type: ignore

    return node

  def format(self, *, ancestors: Literal['all', 'none', 'path'] = 'path'):
    # Path starting from self up to root pool
    pool_path = [self]
    root_pool = self

    if ancestors != 'none':
      while (parent_pool := root_pool._parent_pool):
        pool_path.append(parent_pool)
        root_pool = parent_pool

    # Exclude the first item, then reverse the list, same as pool_path[::-1][1:]
    root_node = root_pool._prepare_format(pool_path[-2::-1] if ancestors == 'path' else [], self)

    if (ancestors != 'none') and root_pool._owning_task:
      root_node = HierarchyNode(root_pool._owning_task.get_name(), [root_node])

    return root_node.format()

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
    return max((-1, *(task_info.depth for task_info in self._tasks.values())))

  def _spawn_from_spec(self, spec: PoolTaskSpec, /):
    assert self._status == 'running'

    task = asyncio.create_task(spec.coro, name=spec.name)
    self._logger.debug(f'Spawning task {task.get_name()} with depth {spec.info.depth}')

    self._tasks[task] = spec.info
    self.__class__._pools_by_task_regular[task] = self

    # Wake up the wait() loop to start awaiting this task
    self._loop_wake_up_event.set()

  async def _wait(self, *, forever: bool):
    cancelling = False
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
        cancelling = True
        self._close()
        continue

      self._loop_wake_up_event.clear()

      # Iterate over all tasks to remove them if they are done
      for task in list(self._tasks.keys()):
        if task.done():
          try:
            exc = task.exception()
          except asyncio.CancelledError:
            # Reached when the pool is being closed
            pass
          else:
            if exc:
              task_info = self._tasks[task]

              # Avoid adding a TraceException to BaseException instances
              if task_info.call_tb and (not task_info.skip_tb_trace) and isinstance(exc, Exception):
                trace_exc = TraceException().with_traceback(task_info.call_tb)

                # Find first exception in causality chain
                current_exc = exc

                while current_exc.__cause__ is not None:
                  current_exc = current_exc.__cause__

                current_exc.__cause__ = trace_exc

              exceptions.append(exc)

          self._logger.debug(f'Collected task {task.get_name()}')

          del self._tasks[task]
          del self.__class__._pools_by_task_regular[task]

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
        # An alternative here could be to set _cancellation_depth to the minimal depth of failed tasks
        self._close()

    self._logger.debug('Closing pool')
    self._status = 'done'

    if self._owning_task and self._parent_pool and (self._parent_pool == self._pools_by_task_regular.get(self._owning_task)):
      self._parent_pool._tasks[self._owning_task].pool = None

    if len(exceptions) >= 2:
      raise BaseExceptionGroup('Pool', exceptions)
    if exceptions:
      raise exceptions[0]
    if cancelling:
      raise asyncio.CancelledError

  def run(self, *, forever: bool = False):
    """
    Run the pool.

    Cancelling this call cancels all tasks in the pool. The pool will be attached to the current task that called this method, not to the task executing the resulting coroutine.

    Parameters
      forever: Whether to keep the pool running once all tasks have finished.
    """

    if self._status != 'idle':
      raise InvalidPoolStatusError('Attempting to run a pool that is not idle')

    self._owning_task = asyncio.current_task()
    self._parent_pool = self.try_current()
    self._status = 'running'

    if self._owning_task and self._parent_pool and (self._parent_pool == self._pools_by_task_regular.get(self._owning_task)):
      self._parent_pool._tasks[self._owning_task].pool = self

    for spec in self._planned_tasks:
      self._spawn_from_spec(spec)

    self._planned_tasks.clear()

    return self._wait(forever=forever)

  def spawn(
    self,
    coro: Coroutine[Any, Any, None],
    /, *,
    _frame_skip: int = 0,
    _skip_tb_trace: bool = False,
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

    info = PoolTaskInfo(
      call_tb=slice_tb_start(create_tb(_frame_skip), 2),
      depth=depth,
      skip_tb_trace=_skip_tb_trace
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
      A `Pool` object.

    Raises
      RuntimeError: If there is no current task or if the current task is not running in a pool.
    """

    pool = cls.try_current()

    if pool is None:
      raise RuntimeError('No current pool')

    return pool

  @classmethod
  def try_current(cls):
    """
    Get the current pool.

    Returns
      A `Pool` object, or `None` if there is no current task or if the current task is not running in a pool.
    """

    current_task = asyncio.current_task()
    return current_task and (
      # First check transient pools because a context could have been created in a task running in a pool
      cls._pools_by_task_context.get(current_task) or
      cls._pools_by_task_regular.get(current_task)
    )

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


    # Create and start the pool

    pool = cls(name)

    # Sets attributes _owning_task and _parent_pool correctly since run() is called before the task is created
    run_task = asyncio.create_task(pool.run(forever=forever))

    root_task = pool._owning_task
    assert root_task


    # Magic

    # Ran afterwards such that run() can obtain the root task and the correct parent pool instead of the new one
    old_context_task_pool = cls._pools_by_task_context.get(root_task)
    cls._pools_by_task_context[root_task] = pool

    if old_context_task_pool:
      assert old_context_task_pool._context_task
      old_context_task_pool._tasks[old_context_task_pool._context_task].pool = pool


    # Build the fake task

    yield_future = Future[None]()

    async def current_task_handler():
      while True:
        try:
          await asyncio.shield(yield_future)
        except asyncio.CancelledError:
          # If the task was cancelled from the outside
          if yield_future.done():
            run_task.cancel()
            raise

          # Otherwise, the pool is being closed
          root_task.cancel()
        else:
          if yield_future.done():
            break

    pool.spawn(current_task_handler(), _frame_skip=2, _skip_tb_trace=True, depth=-1, name='<Asynchronous context manager>')
    pool._context_task = last(pool._tasks.keys())


    # Yield the pool

    try:
      yield pool
    except BaseException as e:
      yield_future.set_exception(e)
    else:
      yield_future.set_result(None)


    # Cleanup

    try:
      await run_task
    finally:
      if old_context_task_pool:
        assert old_context_task_pool._context_task
        cls._pools_by_task_context[root_task] = old_context_task_pool
        old_context_task_pool._tasks[old_context_task_pool._context_task].pool = None
      else:
        del cls._pools_by_task_context[root_task]


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

def walk_tb(tb: TracebackType):
  current_tb = tb

  while current_tb:
    yield current_tb
    current_tb = current_tb.tb_next


@dataclass(slots=True)
class NoValueType:
  pass

NoValue = NoValueType()

def last[T](iterable: Iterable[T], /, default: T | NoValueType = NoValue):
  last_item = default

  for item in iterable:
    last_item = item

  if isinstance(last_item, NoValueType):
    raise ValueError('No items in iterable')

  return cast(T, last_item)


__all__ = [
  'InvalidPoolStatusError',
  'LazyPoolTaskProtocolError',
  'Pool',
  'PoolTaskHandle'
]
