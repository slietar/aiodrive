import asyncio
from signal import Signals

import aiodrive
from aiodrive.modules.process import start_process


async def main():
  try:
    with (
      aiodrive.handle_signal(Signals.SIGINT),
      aiodrive.suppress(aiodrive.ProcessTerminatedException),
    ):
      process = await start_process("sleep 2")
      await process.wait()
  except* aiodrive.SignalHandledException:
    print("\rProcess was interrupted by signal.")


asyncio.run(main())
