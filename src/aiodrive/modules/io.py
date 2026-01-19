import asyncio
from asyncio import StreamReader, StreamReaderProtocol, StreamWriter
from asyncio.streams import FlowControlMixin
import inspect
import sys
from typing import IO, Protocol


async def get_reader(file: IO[bytes], /):
  """
  Get a `StreamReader` for the given file.

  Parameters
  ----------
  file
    The file to read from.

  Returns
  -------
  StreamReader
  """

  reader = StreamReader()
  protocol = StreamReaderProtocol(reader)

  loop = asyncio.get_event_loop()
  await loop.connect_read_pipe(lambda: protocol, file)

  return reader


async def get_writer(file: IO[bytes], /):
  """
  Get a `StreamWriter` for the given file.

  Parameters
  ----------
  file
    The file to write to.

  Returns
  -------
  StreamWriter
  """

  loop = asyncio.get_event_loop()
  transport, protocol = await loop.connect_write_pipe(FlowControlMixin, file)

  return StreamWriter(transport, protocol, None, loop)


class AsyncReader(Protocol):
  async def read(self, n: int = -1) -> bytes:
    ...

class AsyncWriter(Protocol):
  async def write(self, chunk: bytes) -> None:
    ...

if sys.version_info >= (3, 14):
  from io import Writer
else:
  class Writer(Protocol):
    def write(self, chunk: bytes) -> int:
      ...


async def pipe(source: AsyncReader, destination: AsyncWriter | StreamWriter | Writer, /, *, chunk_size: int = 65_536):
  """
  Pipe data from the source to the destination.

  Parameters
  ----------
  source
    The source to read from.
  destination
    The destination to write to.
  chunk_size
    The maximal size of each chunk to read and write.
  """

  while True:
    chunk = await source.read(chunk_size)

    if not chunk:
      break

    if isinstance(destination, StreamWriter):
      destination.write(chunk)
      await destination.drain()
    else:
      result = destination.write(chunk)

      if inspect.isawaitable(result):
        await result


__all__ = [
  'get_reader',
  'get_writer',
  'pipe',
]
