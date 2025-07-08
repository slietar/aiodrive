# Asyncio patterns


## Usage


### Resource factory

Sync + Async variants

Resources are reused

```py
from aiodrive.factory import Factory

async def create_resource():
  ...

async with Factory(create_resource) as factory:
  async with factory.build() as resource:
    resource.use()
```


### Limited task group

```py
from aiodrive.limited_task_group import LimitedTaskGroup

async with LimitedTaskGroup(max_concurrent_count=5) as group:
  group.spawn(some_coroutine)
  group.spawn(another_coroutine)
```


### Latch

```py
from aiodrive.latch import Latch

online_latch = Latch()

async def loop():
  while True:
    await online_latch.wait_set()
    print('Now online')

    await online_latch.wait_unset()
    print('Now offline')

# Somewhere else
online_latch.set()
online_latch.unset()
```


### Signal listener

```py
from aiodrive.signals import cancel_upon_signal, wait_for_signal

signal = await wait_for_signal('SIGINT', 'SIGTERM')

async with cancel_upon_signal('SIGINT', 'SIGTERM'):
    ...
```


### Cancellation

```py
async with cancel_upon(
    asyncio.sleep(5),
):
    ...

# Same as

async with asyncio.timeout(5):
    ...
```


### Calling a function every x seconds, taking into account the execution time of that function

### to_thread but wait for the thread to finish
### to_thread, passing a function that tells whether the task was cancelled - also allowing to use that function as a loop iterable which consumes another iterable
### logging + handle_signals
