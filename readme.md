# aiodrive

**aiodrive** is a Python package for working with asynchronous code powered by `asyncio`.

It only supports Python 3.12 and later.


## Installation

```sh
$ pip install aiodrive
```


## Features

- **`BackgroundExecutor`** – A class that runs tasks in a separate thread, each
  with a dedicated lifetime.
- **`Button`** – A synchronization primitive similar to `asyncio.Event` but that
  resets immediately after being set, useful for triggering waiters.
- **`Latch`** – A synchronization primitive similar to `asyncio.Event` but that
  can be awaited for both set and reset occurences.
- **`NestableLock`** - A lock that can be acquired multiple times if the current
  task already holds it.
- **`OrderedQueue`** – A queue similar to `asyncio.Queue` but that lets
  producers provide items an unordered manner while consumers receive them in
  the order defined by producers.
- **`ThreadSafeEvent`** - A thread-safe variant of `asyncio.Event`.
- **`ThreadTaskGroup`** – A task group that runs tasks in a separate thread.
- **`UnorderedQueue`** – A queue similar to `asyncio.Queue` but with the same
  interface as `OrderedQueue`.

- **`auto_terminated_task_group`** – A task group that automatically terminates
  when the current task is cancelled.
- **`buffer_aiter()`** – Buffer items of an async iterable into a list. (TODO:
  Maybe even concurrently on non-generator iterators?, see
  https://stackoverflow.com/questions/43701647/semantics-of-async-for-can-anext-calls-overlap)
- **`cancel_task()`** – Cancel a task and await it.
- **`collect()`**
- **`contextualize()`** – Run an awaitable as a context manager, ensuring that
  its task is cancelled when the context manager exits.
- **`handle_signal()`** – Register a signal handler that cancels the current
  task when the signal is received.
- **`map_concurrently()`** – Map items of an async iterable concurrently into a
  new async iterable.
- **`prime()`** – Immediately execute as much code of a coroutine as possible
  before it is awaited.
- **`race()`** – Run multiple tasks and return the result of the first one to
  finish, after having cancelled and awaited the other tasks.
- **`repeat_periodically()`** – Create an iterator that yields periodically,
  taking into account the time taken when the yielded value is consumed.
- **`shield()`** – Shield a task against cancellation and await it, unlike
  `asyncio.shield()`.
- **`run_in_thread()`** – Run an awaitable in a separate thread with its
  own event loop.
- **`timeout()`** (TODO: Deprecate) – Run a block of code with a timeout, unlike
  `asyncio.wait_for()` which only supports a single awaitable.
- **`try_all()`** – Run multiple tasks and cancel those still running if one of
  them raises an exception.
- **`wait_all()`** – Run multiple tasks without cancelling any if one raises an
  exception.
- **`wait_for_signal()`** – Wait for a signal.
<!-- - **`wrap_anext()**` - Wrap every iteration of an async iterator with an
  abstract context manager.
  Not sure about that one - this is could also exist for sync iterators on sync context managers, and yet this use case never came up.
  -->
- **`zip_concurrently()`** – Zip multiple async iterables concurrently into a
  new async iterable.


## Examples


### Running a spinner on a separate thread

```py
async def spinner(interval: float):
  async for (_, index) in zip_concurrently(
    repeat_periodically(interval),
    ensure_aiter(itertools.count()),
  ):
    print("Loading... " + ["|", "/", "-", "\\"][index % 4])

async with contextualize(run_in_thread(spinner(interval=0.1))):
  # Do blocking work here
  ...
```


## Usage

### SmartLock

Priority system?
Thread-safe

```py
from aiodrive import SmartLock

# priority_resolution = fifo, random, max_acquired_count+fifo
lock = SmartLock()

# mode = exclusive, shared
# scope = none, task (not useful), thread, context (not a subset nor superset of task and thread)
# weak = True/False
async with lock.acquire(mode="exclusive", scope="thread"):
  pass

# Alternative

async with lock.exclusive():
  ...

async with lock.shared():
  ...

async with lock.thread_shared():
  ...

# The current task may be cancelled if another task asks for the lock
# Only acquired once only weak tasks are waiting (or no tasks at all)
async with lock.weak_exclusive():
  ...

# Blocking variants for use outside of an asyncio event loop

with lock.exclusive()
with lock.shared()
with lock.thread_shared()
# with lock.weak_exclusive() - Does not exist
```
