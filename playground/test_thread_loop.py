import asyncio
import sys
import time
import warnings

import aiodrive


warnings.resetwarnings()

async def a():
    # time.sleep(1)
    # sys.exit(1)
    # raise SystemExit(2)
    # raise BaseException("Test exception")
    await asyncio.sleep(1)
    raise Exception("Test exception inside task")

async def main():
    task = asyncio.create_task(aiodrive.run_in_thread_loop(a()))
    await asyncio.sleep(1.0)
    task.cancel()
    await task

    # # task = asyncio.create_task(a())
    # print("Created task")

    # try:
    #     await asyncio.sleep(1)
    # finally:
    #     await task


# import asyncio
# asyncio.run(main())
asyncio.run(main())
print("Done")


# try:
#     raise Exception("Test exception")
# except:
#     pass
# finally:
#     print(">>", repr(sys.exception()))
