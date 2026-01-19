import asyncio

import aiodrive


if __name__ == "__main__":
  @aiodrive.primed
  async def a(x: int):
    print("In a")
    await asyncio.sleep(1)
    raise Exception("Test")
    return x + 2

  import asyncio

  async def main():
    await a(3)
    # await asyncio.sleep(2)

  loop = asyncio.new_event_loop()

  loop.run_until_complete(aiodrive.prime(a(3), loop=loop))
  # loop.run_until_complete(main())
  # asyncio.run(main())


__all__ = [
  'prime',
]
