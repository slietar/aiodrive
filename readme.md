# aiodrive

**aiodrive** is a Python package for working with asynchronous code powered by `asyncio`. It only works on 3.12 and later.


## Installation

```sh
$ pip install aiodrive
```


## Pools

A _pool_ is a collection of tasks that run at the same time. If any task fails, all other tasks are cancelled and all errors are raised, using an `ExceptionGroup` if necessary. If the parent task is cancelled, all tasks in the pool are cancelled as well.

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


## Latch events

A _latch event_ is an object similar to `asyncio.Event` that can be watched for both its set and unset states.

```py
online_event = LatchEvent()

async def loop():
  while True:
    await online_event.wait_set()
    print('Now online')

    await online_event.wait_unset()
    print('Now offline')

# Somewhere else
online_event.set()
online_event.unset()
```


## Utility functions

- `aexit_handler()` – Decorate an asynchronous context manager's `__aexit__()` method for it to collect both exceptions raised inside the method and by the context manager's consumer.
- `cancel_task()` – Cancel a task and await it.
- `prime()` – Immediately execute as much as code as possible of a coroutine before it is awaited.
- `race()` – Run multiple tasks and return the result of the first one to finish, after having cancelled and awaited the other tasks.
- `shield()` – Shield a task against cancellation and await it, unlike `asyncio.shield()`.
- `timeout()` – Run a block of code with a timeout, unlike `asyncio.wait_for()` which only supports a single awaitable.
- `try_all()` – Run multiple tasks and cancel those still running if one of them raises an exception.
- `wait_all()` – Run multiple tasks without cancelling any if one raises an exception.
