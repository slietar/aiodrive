import asyncio
import contextlib


class TaskGroupTerminatedException(Exception):
    pass

@contextlib.asynccontextmanager
async def auto_terminated_task_group():
    try:
        async with asyncio.TaskGroup() as group:
            yield group
            raise TaskGroupTerminatedException
    except* TaskGroupTerminatedException:
        pass
