import asyncio
from asyncio import StreamReader, StreamWriter
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv6Address
from typing import Optional, override

from .handle import using_pending_daemon_handle
from .shield import ShieldContext
from .task_group import eager_task_group


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
  bindings: Iterable[SockName]

  @staticmethod
  @using_pending_daemon_handle
  async def listen(
    handler: Callable[[Connection], Awaitable[None]],
    host: Sequence[str] | str,
    *,
    port: Optional[int] = None,
  ):
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
      The port to bind to. Defaults to delegating allocation to the operating
      system.

    Returns
    -------
    AbstractAsyncContextManager[TCPServer]
      An async context manager that yields the created TCP server. The server is
      closed when the context manager exits. This is done in two steps:

      1. The server stops accepting new connections.
      1. Existing connection handlers are cancelled, leading to the closure of
         their connections once they return.
    """

    context = ShieldContext()

    def handle_connection_sync(reader: StreamReader, writer: StreamWriter):
      group.create_task(handle_connection_async(reader, writer))

    async def handle_connection_async(reader: StreamReader, writer: StreamWriter):
      context = ShieldContext()

      try:
        await handler(Connection(
          SockName.parse(writer.transport.get_extra_info('peername')),
          SockName.parse(writer.transport.get_extra_info('sockname')),
          reader,
          writer,
        ))
      finally:
        writer.close()
        await context.shield(writer.wait_closed())

    server = await asyncio.start_server(handle_connection_sync, host, port)

    try:
      async with eager_task_group() as group:
        try:
          yield TCPServer(
            bindings=[SockName.parse(sock.getsockname()) for sock in server.sockets],
          )
        finally:
          server.close()
    finally:
      await context.shield(server.wait_closed())


__all__ = [
  'Connection',
  'SockName',
  'TCPServer',
]
