import asyncio
from asyncio import StreamReader, StreamReaderProtocol, StreamWriter
from asyncio.streams import FlowControlMixin
from typing import IO


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


async def pipe(source: StreamReader, destination: StreamWriter, /, *, chunk_size: int = 65_536):
  """
  Pipe data from the source to the destination.

  Parameters
  ----------
  source
    The source to read from.
  destination
    The destination to write to.
  chunk_size
    The size of each chunk to read and write.
  """

  while True:
    chunk = await source.read(chunk_size)

    if not chunk:
      break

    destination.write(chunk)
    await destination.drain()


__all__ = [
  'get_reader',
  'get_writer',
  'pipe',
]
