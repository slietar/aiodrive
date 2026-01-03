# Aiodrive

Aiodrive is a Python package for working with asynchronous code powered by `asyncio` and that relies on structured concurrency. It provides various utilities for managing tasks, ensuring programs are gracefully terminated, producing and consuming iterators, and coordinating between threads and asynchronous code.

It supports Python 3.12 and later.


## Installation

Aiodrive is available on PyPI under the name `aiodrive`.


## API

<!-- - **`ThreadTaskGroup`** – A task group that runs tasks in a separate thread. -->

<!-- - **`OrderedQueue`** – A queue similar to `asyncio.Queue` but that lets producers provide items an unordered manner while consumers receive them in the order defined by producers.
- **`UnorderedQueue`** – A queue similar to `asyncio.Queue` but with the same interface as `OrderedQueue`. -->

- Managing multiple awaitables
  - **`amass()`**<br>Create an asynchronous generator that yields results from awaitables as they complete.
  - **`gather()`**<br>Concurrently collect results from multiple awaitables.
  - **`race()`**<br>Wait for the fastest of a given set of awaitables.
  - **`volatile_task_group()`**<br>Create a task group that automatically terminates when exiting the context.
- Managing individual awaitables
  - **`GuaranteedTask`**<br>A variant of `asyncio.Task` that that guarantees that the provided awaitable is awaited before any cancellation occurs.
  - **`ShieldContext`**<br>A class for shielding awaitables from cancellation based on the cancellation request count at the time of instantiation.
  - **`cancel_task()`**<br>Cancel and await the provided task.
  - **`prime()`**<br>Prime an awaitable such that as much code as possible is executed immediately.
  - **`primed()`**<br>Decorate the given function such that it returns a primed awaitable.
  - **`shield()`**<br>Shield an awaitable from cancellation.
  - **`shield_wait()`**<br>Shield and await a given awaitable.
  - **`shield_wait_forever()`**<br>  Shield and await the provided awaitable indefinitely, ignoring all cancellation requests.
- Managing async iterators
  - **`auto_aclosing()`**<br>Create an async context manager that calls the `aclose` method, if any, on the provided object upon exit.
  - **`auto_closing()`**<br>Create a context manager that calls the `close` method, if any, on the provided object upon exit.
  - **`buffer_aiter()`**<br>Create an asynchronous generator that prefetches items from the given async iterable.
  - **`collect()`**<br>Collect items of an async iterable into a list.
  - **`ensure_aiter()`**<br>Create an asynchronous iterator from the provided synchrounous or asynchronous iterable.
  - **`ensure_daemon()`**<br>Create a new awaitable that raises an exception if the given awaitable returns.
  - **`map()`**<br>Map an iterable or asynchronous iterable to an asynchronous iterable using the given asynchronous mapper function.
  - **`reduce()`**<br>Reduce the items from the provided asynchronous iterable.
  - **`zip_concurrently()`**<br>Zip multiple asynchronous iterables together, yielding tuples of items from each iterable.
- Creating context managers
  - **`DaemonHandle`**<br>A class that manages the awaiting and cancellation of a daemon awaitable.
  - **`PendingDaemonHandle`**<br>A class that manages the initialization, awaiting and cancellation of a daemon awaitable.
  - **`bivalent_context_manager()`**<br>Create a function that returns a context manager which can be used both synchronously and asynchronously.
  - **`cleaned_up()`**<br>Create a context manager that calls the given asynchronous callback when exiting the context.
  - **`concurrent_contexts()`**<br>Run multiple context managers concurrently.
  - **`contextualize()`**<br>Transform an awaitable into an asynchronous context manager.
  - **`suppress()`**<br>Suppress the specified exceptions in an asynchronous context.
  - **`use_scope()`**<br>Create a context that locally manages the cancellation of the current task.
  - **`using_pending_daemon_handle()`**<br>Decorate the provided function such that it returns a `PendingDaemonHandle`.
- Managing the program
  - **`handle_signal()`**<br>Register a signal handler that cancels the current task when the signal is received.
  - **`run()`**<br>Run an awaitable in a new event loop with enforced structured concurrency.
  - **`wait_for_signal()`**<br>Wait for a signal.
- Working with threads
  - **`Latch`**<br>A primitive similar to `asyncio.Event` but that can be awaited for both set and reset occurences.
  - **`ThreadsafeLock`**<br>A lock that can be acquired from different threads.
  - **`ThreadsafeState`**<br>A thread-safe primitive for storing and watching a state.
  <!-- - **`threadsafe_aiter()`**<br>Create an async iterator that can be consumed from a different thread than the one producing items. -->
  <!-- - **`threadsafe_agen()`**<br>Create an async generator that can be consumed from a different thread than the one producing items. -->
  - **`launch_in_thread_loop()`**<br>Launch an awaitable in a separate thread with its own event loop.
  - **`run_in_thread_loop()`**<br>Run an awaitable in a separate thread with its own event loop.
  - **`run_in_thread_loop_contextualized()`**<br>Run an awaitable in a separate thread with its own event loop, using a context manager.
- Creating awaitables
  - **`checkpoint()`**<br>Check that the current task was not cancelled.
  - **`repeat_periodically()`**<br>Create an iterator that yields periodically.
  - **`suspend()`**<br>Wait for the next iteration of the event loop.
  - **`wait_forever()`**<br>Wait indefinitely.
- Primitives
  - **`ConcreteAwaitable`**<br>An awaitable created from an `__await__` function.
  - **`FutureState`**<br>A primitive for storing a future's state.
  - **`Button`**<br>A class that wakes up registered waiters when called.
  - **`Cargo`**<br>A class that wakes up registered waiters with a value when called with that value.
  - **`get_event_loop()`**<br>Get the current event loop, if any.
  - **`set_event_loop()`**<br>Set the current event loop.
- Working with I/O events
  - **`KqueueKqueueEventManager`**<br>Create a context manager for receiving kqueue events.
  - **`watch_path()`**<br>Watch a filesystem path.
- Networking
  - **`TCPServer`**<br>A TCP server.
- Miscellaneous
  - **`NestableLock`**<br>A lock that can be held simultaneously by different callers in the same context.


## Notes

Unless specified otherwise, the following requirements and guarantees apply:

- There is no implicit cleanup treatment of async generators, which is unlike certain libraries like [`asyncstdlib`](https://asyncstdlib.readthedocs.io/en/stable/index.html#async-iterator-cleanup). If required, as is the case for certain functions such as `buffer_aiter()`, generators must be closed explicitly. For example:
  ```py
  agen = get_some_async_generator()

  async with contextlib.aclosing(agen):
    async for item in agen:
      if some_condition:
        break

    # The generator may not be exhausted here and will therefore be closed by contextlib.aclosing().
  ```
- Awaitables provided as arguments to a function are guaranteed to be awaited as long as the function itself is awaited.
- Awaitables provided as arguments are awaited exactly once.
- Awaitables returned by functions may only be awaited once.
- Asynchronous iterator provided as arguments are guaranteed to only have their `__anext__()` called once at a time.
- Returned asynchronous iterators may only have their `__anext__()` called once at a time.
- Returned awaitables may be wrapped as tasks using an eager task factory.
- Arguments must belong to the same event loop as the one in which the function or class is used. Classes must be instantiated and used in the same event loop.
- Functions and classes have a well-defined behavior for at least one cancellation. Some functions and classes support an arbitrary number of cancellations.
- The `__len__()` method of argument iterables, if any, is maintained on the returned iterables whenever possible.
