# aiodrive

**aiodrive** is a Python package for working with asynchronous code powered by `asyncio`.

It only supports Python 3.12 and later.

TODO: ThreadSafeFuture as new synchronization primitive


## Installation

```sh
$ pip install aiodrive
```


## Features

- **`AutoTerminatedTaskGroup`** – A task group that automatically terminates
- **`BackgroundExecutor`** – A class that runs tasks in a separate thread, each
  with a dedicated lifetime.
  when the current task is cancelled.
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

- **`cancel_task()`** – Cancel a task and await it.
- **`handle_signal()`** – Register a signal handler that cancels the current
  task when the signal is received.
- **`prime()`** – Immediately execute as much code of a coroutine as possible
  before it is awaited.
- **`race()`** – Run multiple tasks and return the result of the first one to
  finish, after having cancelled and awaited the other tasks.
- **`repeat_periodically()`** – Create an iterator that yields periodically,
  taking into account the time taken when the yielded value is consumed.
- **`shield()`** – Shield a task against cancellation and await it, unlike
  `asyncio.shield()`.
- **`timeout()`** – Run a block of code with a timeout, unlike
  `asyncio.wait_for()` which only supports a single awaitable.
- **`try_all()`** – Run multiple tasks and cancel those still running if one of
  them raises an exception.
- **`wait_all()`** – Run multiple tasks without cancelling any if one raises an
  exception.
- **`wait_for_signal()`** – Wait for a signal.


## Usage

### Pools

A _pool_ is a collection of tasks that run at the same time. If any task fails, all other tasks are cancelled and all exceptions are re-raised, in an `ExceptionGroup` if necessary. If the parent task is cancelled, all tasks in the pool are cancelled as well.

The easiest way to create a pool is to use the `Pool.open()` asynchronous context manager.

```py
from aiodrive import Pool

async def job1():
  ...

async def job2():
  ...

async with Pool.open() as pool:
  pool.spawn(job1())
  pool.spawn(job2())
```

An alternative is to use the `Pool()` constructor and the `Pool.run()` method.

```py
pool = Pool()

pool.spawn(job1())
pool.spawn(job2())

await pool.run()

# Or if there is no event loop running

asyncio.run(pool.run())
```

### Utility functions


### BackgroundExecutor

```py
from aiodrive import BackgroundExecutor

# Ran on another thread
async def log_periodically():
  while True:
    print("Logging...")
    await asyncio.sleep(1)

async with BackgroundExecutor() as executor:
  async with executor.spawn(log_periodically()):
    # Block the main thread
    time.sleep(5)

# The thread is closed when the context manager exits, or if it was never entered, when the last task completes.
```


### SmartLock

Priority system?
Thread-safe

```py
from aiodrive import SmartLock

lock = SmartLock()

async with lock.exclusive():
  ...

async with lock.shared():
  ...

async with lock.thread_shared():
  ...

# The current task may be cancelled if another task asks for the lock
async with lock.weak_exclusive():
  ...

# Blocking variants for use outside of an asyncio event loop

with lock.exclusive()
with lock.shared()
with lock.thread_shared()
with lock.weak_exclusive()
```
