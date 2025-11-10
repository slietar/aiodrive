# Aiodrive

Aiodrive is a Python package for working with asynchronous code powered by `asyncio`. It provides various utilities for producing and consuming iterators, managing tasks, and coordinating between threads and asynchronous code.

It supports Python 3.12 and later.


## Installation

Aiodrive is available on PyPI under the name `aiodrive`.


## API

<!-- - **`ThreadTaskGroup`** – A task group that runs tasks in a separate thread. -->

<!-- - **`OrderedQueue`** – A queue similar to `asyncio.Queue` but that lets producers provide items an unordered manner while consumers receive them in the order defined by producers.
- **`UnorderedQueue`** – A queue similar to `asyncio.Queue` but with the same interface as `OrderedQueue`. -->

<!-- - **`map_concurrently()`**<br>Map items of an async iterable concurrently into a new async iterable. -->

- **`Button`**<br>A primitive similar to `asyncio.Event` but that resets immediately after being set, useful for triggering waiters.
- **`Cargo`**<br>A primitive similar to `Button` but that carries a value.
- **`FutureState`**<br>A primitive for storing a future's state.
- **`GuaranteedTask`**<br>A variant of `asyncio.Task` that is guaranteed to be awaited before any cancellation can happen.
- **`Latch`**<br>A primitive similar to `asyncio.Event` but that can be awaited for both set and reset occurences.
- **`NestableLock`**<br>A lock that can be held simultaneously by different callers in the same context.
- **`ThreadsafeButton`**<br>A thread-safe variant of `Button`.
- **`ThreadsafeState`**<br>A thread-safe primitive for storing and watching a state.
- **`ThreadsafeLock`**<br>A lock that can be acquired from different threads.
- **`run()`**<br>Run an awaitable in a new event loop while enforcing structured concurrency.
- **`buffer_aiter()`**<br>Pre-fetch items of an async iterable.
- **`cancel_task()`**<br>Cancel a task and await it.
- **`cleanup_shield()`**<br>Shield a task against cancellation if it has not been cancelled yet, and await it.
- **`collect()`**<br>Collect items of an async iterable into a list.
- **`concurrent_contexts()`**<br>Run multiple context managers concurrently.
- **`contextualize()`**<br>Run an awaitable as a context manager, ensuring that its task is cancelled when the context manager exits.
- **`eager_task_group()`**<br>Create a task group that automatically terminates when the current task exits the associated context manager.
- **`ensure_aiter()`**<br>Ensure that the provided iterable is an async iterable.
- **`ensure_correct_cancellation()`**<br>Ensure that an `asyncio.CancelledError` is re-raised if the current task has been cancelled.
- **`handle_signal()`**<br>Register a signal handler that cancels the current task when the signal is received.
- **`launch_in_thread_loop()`**<br>Launch an awaitable in a separate thread with its own event loop.
- **`prime()`**<br>Immediately execute as much code of a coroutine as possible before it is awaited.
- **`primed()`**<br>Decorate the given function such that it returns a primed awaitable.
- **`race()`**<br>Run multiple tasks and return the result of the first one that finishes, after having cancelled and awaited the other tasks.
- **`repeat_periodically()`**<br>Create an iterator that yields periodically, taking into account the time taken when the yielded value is consumed.
- **`run_in_thread_loop_contextualized()`**<br>Run an awaitable in a separate thread with its own event loop, using a context manager.
- **`run_in_thread_loop()`**<br>Run an awaitable in a separate thread with its own event loop.
- **`shield()`**<br>Shield a task against cancellation and await it.
- **`suppress()`**<br>A context manager that suppresses specified exceptions, ensuring that an `asyncio.CancelledError` is re-raised if necessary.
- **`try_all()`**<br>Run multiple tasks and cancel those still running if one of them raises an exception.
- **`use_scope()`**<br>Create a context manager that allows for a silent cancellation of the current task.
- **`wait_all()`**<br>Run multiple tasks without cancelling any if one raises an exception.
- **`wait_for_signal()`**<br>Wait for a signal.
- **`zip_concurrently()`**<br>Zip multiple async iterables concurrently into a new async iterable.


## Notes

- There is no implicit cleanup treatment of async generators, which is unlike certain libraries like [`asyncstdlib`](https://asyncstdlib.readthedocs.io/en/stable/index.html#async-iterator-cleanup). If required, as is the case for certain functions such as `buffer_aiter()`, generators must be closed explicitly. For example:
  ```py
  agen = get_some_async_generator()

  async with contextlib.aclosing(agen):
    async for item in agen:
      if some_condition:
        break

    # The generator may not be exhausted here and must therefore be closed explicitly.
  ```
- If a function accepts an awaitable, it is guaranteed to be awaited as long as the function itself is awaited.
- Awaitables accepted as arguments are awaited exactly once.
- Awaitables returned by functions may only be awaited once.
- Only a single call to an async iterator's `__anext__()` method is ever pending at a time. The same is expected from consumers of a returned async iterator.
- Unless stated otherwise, functions and classes may not be used across multiple event loops.
- All functions and classes support using an eager task factory.
