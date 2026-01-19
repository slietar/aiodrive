import asyncio

import aiodrive


x = [1, 2, 3]


if __name__ == "__main__":
  async def main():
    async def gen(delay: float, value: int):
      await asyncio.sleep(delay)
      return value

    async def fail(delay: float):
      await asyncio.sleep(delay)
      raise ValueError("Intentional failure")

    async for result in aiodrive.amass([
      # gen(1.5, 3),
      # gen(.5, 1),
      # gen(1, 2),
      # fail(0.75),
      # fail(0.75),
    ], sensitive=False):
      print("Got result:", result)

    print("ok")

    # current_task = asyncio.current_task()
    # assert current_task is not None

    # current_task.cancel()
    # print(current_task.cancelling())
    # current_task.cancel()
    # print(current_task.cancelling())

    # try:
    #   await asyncio.sleep(1)
    # except asyncio.CancelledError:
    #   print(current_task.cancelling())

    # try:
    #   await asyncio.sleep(1)
    # except asyncio.CancelledError:
    #   print(current_task.cancelling())
    # else:
    #   print("Not cancelled")

    # async def a():
    #   raise asyncio.CancelledError

    # try:
    #   # await asyncio.sleep(1)
    #   await a()
    # except asyncio.CancelledError:
    #   pass

    # asyncio.current_task().uncancel()
    # await asyncio.sleep(1)


  asyncio.run(main())
