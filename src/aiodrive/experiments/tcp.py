import asyncio
import contextlib
import os
import signal
from asyncio import StreamReader, StreamWriter, TaskGroup
from collections.abc import Awaitable, Callable, Sequence
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
class TCPServer:
  bindings: frozenset[SockName]

  @classmethod
  @contextlib.asynccontextmanager
  async def listen(cls, handler: Callable[[Connection], Awaitable[None]], host: Sequence[str] | str, *, port: Optional[int] = None):
    """
    Create a TCP server.

    Parameters
    ----------
    handler
      A function that is called for each new connection. The connection is
      closed, if not already closed, when the handler returns.
    host
      The host or hosts to bind to.
    port
      The port to bind to.

    Returns
    -------
    AbstractAsyncContextManager[TCPServer]
      An async context manager that yields the created TCP server. The server is
      closed when the context manager exits. This is done in three steps: (1)
      the server stops accepting new connections (2) existing connections
      handlers are cancelled, leading to the closure of their connections (3)
      the server is closed.
    """

    def handle_connection_sync(reader: StreamReader, writer: StreamWriter):
      group.create_task(handle_connection_async(reader, writer))

    async def handle_connection_async(reader: StreamReader, writer: StreamWriter):
      try:
        await handler(Connection(
          SockName.parse(writer.transport.get_extra_info('peername')),
          SockName.parse(writer.transport.get_extra_info('sockname')),
          reader,
          writer,
        ))
      finally:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_connection_sync, host, port)

    bindings = frozenset({
      SockName.parse(sock.getsockname()) for sock in server.sockets
    })

    try:
      async with TaskGroup() as group:
        try:
          yield cls(bindings)
        finally:
          server.close()
    finally:
      await server.wait_closed()


# ----


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
          print('Exiting')
        # await asyncio.sleep(5)

      async with TCPServer.listen(handler, 'localhost', port=8995) as server:
        for binding in server.bindings:
          print('Listening on', binding)

        await asyncio.Future()

  except* SignalHandledException:
    print('Shutting down gracefully...')

asyncio.run(main())
