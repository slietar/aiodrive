import asyncio
import logging
import math
from pathlib import Path
import sys
import traceback

from .pool import Pool


# logging.basicConfig(level=logging.DEBUG)


async def delayed_cancellation(coro):
  task = asyncio.create_task(coro)

  try:
    await asyncio.shield(task)
  except asyncio.CancelledError:
    await asyncio.sleep(0.5)
    await task
    raise

async def failing(coro):
  await coro
  raise Exception('Failing')


if __name__ == '__main__':
  pool = Pool('Pool')

  # async def a():
  #   async with Pool.open() as pool:
  #     pool.spawn(failing(asyncio.sleep(1)))
  #     # raise Exception

  async def start():
    async with Pool.open('Pool') as pool:
      async with Pool.open('Subpool') as subpool:
        # print(subpool.format())
        pass

        print(pool.format(ancestors='all'))


  async def main():
    async with Pool.open('Root') as pool:
      pool.spawn(asyncio.sleep(0.1))
      pool.spawn(start())

  asyncio.run(main())
