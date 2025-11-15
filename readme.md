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

- Tools for managing multiple awaitables
  - **`amass()`**<br>Create an asynchronous iterator that yields results from awaitables as they complete.
  - **`gather()`**<br>Concurrently collect results from multiple awaitables.
  - **`race()`**<br>Wait for the fastest of a given set of awaitables.
  - **`volatile_task_group()`**<br>Create a task group that automatically terminates when exiting the context.
- Tools for managing individual awaitables
  - **`GuaranteedTask`**<br>A variant of `asyncio.Task` that that guarantees that the provided awaitable is awaited before any cancellation occurs.
  - **`cancel_task()`**<br>Cancel and await the provided task.
  - **`prime()`**<br>Prime an awaitable such that as much code as possible is executed immediately.
  - **`primed()`**<br>Decorate the given function such that it returns a primed awaitable.
  - **`shield()`**<br>Shield and await a given awaitable.
- Tools for managing async iterators
  - **`buffer_aiter()`**<br>Pre-fetch items of an async iterable.
  - **`collect()`**<br>Collect items of an async iterable into a list.
  - **`ensure_aiter()`**<br>Ensure that the provided iterable is an async iterable.
  - **`reduce()`
  - **`zip_concurrently()`**<br>Zip multiple async iterables concurrently into a new async iterable.
- Tools for managing context managers
  - **`concurrent_contexts()`**<br>Run multiple context managers concurrently.
  - **`contextualize()`**<br>Run an awaitable as a context manager, ensuring that its task is cancelled when the context manager exits.
  - **`suppress()`**<br>A context manager that suppresses specified exceptions, ensuring that an `asyncio.CancelledError` is re-raised if necessary.
  - **`use_scope()`**<br>Create a context manager that allows for a silent cancellation of the current task.
- Tools for managing the overall program
  - **`wait_for_signal()`**<br>Wait for a signal.
  - **`handle_signal()`**<br>Register a signal handler that cancels the current task when the signal is received.
  - **`run()`**<br>Run an awaitable in a new event loop while enforcing structured concurrency.
- Tools for working with threads
  - **`Latch`**<br>A primitive similar to `asyncio.Event` but that can be awaited for both set and reset occurences.
  <!-- - **`threadsafe_aiter()`**<br>Create an async iterator that can be consumed from a different thread than the one producing items. -->
  <!-- - **`threadsafe_agen()`**<br>Create an async generator that can be consumed from a different thread than the one producing items. -->
  - **`run_in_thread_loop_contextualized()`**<br>Run an awaitable in a separate thread with its own event loop, using a context manager.
  - **`run_in_thread_loop()`**<br>Run an awaitable in a separate thread with its own event loop.
  - **`launch_in_thread_loop()`**<br>Launch an awaitable in a separate thread with its own event loop.
  - **`ThreadsafeState`**<br>A thread-safe primitive for storing and watching a state.
  - **`ThreadsafeLock`**<br>A lock that can be acquired from different threads.
- Primitives
  - **`FutureState`**<br>A primitive for storing a future's state.
  - **`Button`**<br>A primitive similar to `asyncio.Event` but that resets immediately after being set, useful for triggering waiters.
  - **`Cargo`**<br>A primitive similar to `Button` but that carries a value.
- Miscellaneous
  - **`NestableLock`**<br>A lock that can be held simultaneously by different callers in the same context.
  - **`repeat_periodically()`**<br>Create an iterator that yields periodically, taking into account the time taken when the yielded value is consumed.



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
- All functions and classes support at least one cancellation. Some functions and classes support an arbitrary number of cancellations.
