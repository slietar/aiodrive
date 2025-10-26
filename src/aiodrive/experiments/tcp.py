import asyncio
import contextlib
import signal
from asyncio import Queue, QueueEmpty, QueueFull, StreamReader, StreamWriter
from collections.abc import Sequence
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv6Address
from typing import Optional, override

from ..modules.signals import SignalHandledException, handle_signal


@dataclass(frozen=True, slots=True)
class SockName:
  address: IPv4Address | IPv6Address
  port: int

  @override
  def __str__(self):
    match self.address:
      case IPv4Address():
        return f'{self.address}:{self.port}'
      case IPv6Address():
        return f'[{self.address}]:{self.port}'

  @classmethod
  def parse(cls, name: tuple, /):
    match name:
      case host, port:
        addr = IPv4Address(host)
      case host, port, _flowinfo, _scopeid:
        addr = IPv6Address(host)
      case _:
        raise ValueError(f'Invalid peername: {name}')

    return cls(addr, port)


@dataclass(slots=True)
class Connection:
  client_name: SockName
  server_name: SockName

  reader: StreamReader = field(repr=False)
  writer: StreamWriter = field(repr=False)


@dataclass(slots=True)
class TcpServer:
  bindings: frozenset[SockName]
  _queue: Queue[tuple[StreamReader, StreamWriter]]

  async def __aiter__(self):
    while True:
      reader, writer = await self._queue.get()
      socket = writer.transport.get_extra_info('socket')

      client_name = SockName.parse(socket.getpeername())
      server_name = SockName.parse(socket.getsockname())

      info = Connection(
        client_name,
        server_name,

        reader,
        writer,
      )

      yield info

  @classmethod
  @contextlib.asynccontextmanager
  async def listen(cls, host: Sequence[str] | str, *, port: Optional[int] = None):
    queue = Queue[tuple[StreamReader, StreamWriter]]()

    def handle_connection_sync(reader: StreamReader, writer: StreamWriter):
      try:
        queue.put_nowait((reader, writer))
      except QueueFull:
        writer.close()

    server = await asyncio.start_server(handle_connection_sync, host, port)

    bindings = frozenset({
      SockName.parse(sock.getsockname()) for sock in server.sockets
    })

    try:
      yield cls(bindings, queue)
    finally:
      server.close()

      try:
        while True:
          _reader, writer = queue.get_nowait()
          writer.close()
      except QueueEmpty:
        pass

      await server.wait_closed()


async def main():
  try:
    with handle_signal(signal.SIGINT):
      async with TcpServer.listen('localhost', port=8995) as server:
        for binding in server.bindings:
          print('Listening on', binding)

        async for conn in server:
          print('New connection from', conn.client_name)
  except* SignalHandledException:
    print('Shutting down gracefully...')


import asyncio

asyncio.run(main())
