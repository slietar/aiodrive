import asyncio

from aiodrive.modules.map import map


async def main():
  async def sleep(label: str, delay: int):
    await asyncio.sleep(delay)
    return f"Task {label} completed after {delay} seconds"

  async def test():
    yield "A"
    await asyncio.sleep(0.2)
    yield "B"
    await asyncio.sleep(0.3)
    yield "C"

  async def mapper(a: str):
    await asyncio.sleep({
      "A": 0.8,
      "B": 0.1,
      "C": 0.2,
    }[a])
    return a.upper()

  x = map(mapper, test(), ordered=False)

  async for result in x:
    print(result)


asyncio.run(main())
