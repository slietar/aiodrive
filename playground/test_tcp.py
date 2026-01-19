import asyncio
import os
import signal

from aiodrive.modules.tcp import Connection, TCPServer
from aiodrive.modules.signals import SignalHandledException, handle_signal


async def main():
  print(os.getpid())

  try:
    with handle_signal(signal.SIGINT):
      async def handler(conn: Connection):
        print('New connection from', conn.client_name)

        try:
          while await conn.reader.read(1024):
            print('Waiting for data...')
        finally:
          print('Exiting client')

      async with TCPServer.listen(handler, 'localhost', port=8995) as server:
        for binding in server.bindings:
          print('Listening on', binding)

        try:
          await asyncio.Future()
        finally:
          print('Exiting server')

  except* SignalHandledException:
    print('Done')

asyncio.run(main())
