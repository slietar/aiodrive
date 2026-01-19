import asyncio
import logging

from aiodrive.modules.watch import watch_path


if __name__ == "__main__":
    async def main():
        logging.basicConfig(level=logging.DEBUG)

        async with watch_path('playground/a/b/c', print):
            await asyncio.Future()

    asyncio.run(main())
