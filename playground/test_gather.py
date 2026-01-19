import aiodrive


if __name__ == "__main__":
  import asyncio

  # async def a():
  #   await asyncio.sleep(1)
  #   print("A done")
  #   raise ValueError("Test error in a")
  #   return 43

  async def main():
    async def a():
      import sys
      sys.exit(1)
      # raise ValueError("Test error in a")

    await aiodrive.gather(a())


    # result = await wait(
    #   a(),
    #   asyncio.sleep(2),
    #   sensitive=False,
    # )

    # print("Results:", result)

    # async with asyncio.TaskGroup() as tg:
    #   tg.create_task(a())
    #   tg.create_task(asyncio.sleep(2))

  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("Cancelled by user")
    raise
