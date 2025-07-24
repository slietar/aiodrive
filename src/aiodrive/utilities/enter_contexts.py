from asyncio import TaskGroup
from collections.abc import Iterable
import contextlib


@contextlib.asynccontextmanager
async def enter_contexts_parallel(contexts: Iterable[contextlib.AbstractAsyncContextManager]):
    async with contextlib.AsyncExitStack() as stack:
        async with TaskGroup() as group:
            # TODO: Replace with run_all()
            tasks = [group.create_task(stack.enter_async_context(context)) for context in contexts]

        yield tuple(task.result() for task in tasks)
