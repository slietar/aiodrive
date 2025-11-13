from collections.abc import Awaitable, Callable
import contextlib

from .shield import ShieldContext


@contextlib.asynccontextmanager
async def cleaned_up(callback: Callable[[], Awaitable[None]], /):
  context = ShieldContext()

  try:
    yield
  finally:
    await context.shield(callback())


if __name__ == "__main__":
  import asyncio

  async def run_cleanup():
    print("Cleaning up...")
    await asyncio.sleep(1)
    print("Cleanup done.")

  async def main():
    async with cleaned_up(run_cleanup):
      print("Doing work...")
      await asyncio.sleep(1)

  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("Cancelled by user")
