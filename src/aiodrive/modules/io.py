import asyncio
import contextlib
import functools
import os
import sys
import termios
import tty
from asyncio import StreamReader, StreamReaderProtocol, StreamWriter
from asyncio.streams import FlowControlMixin
from collections.abc import Callable
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

  loop = asyncio.get_running_loop()
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

  loop = asyncio.get_running_loop()
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


@contextlib.contextmanager
def file_blocking(file: IO[bytes], /, blocking: bool):
  """
  Set the blocking mode of a file.

  The initial blocking mode is restored when exiting the context.

  Parameters
  ----------
  file
    The file to set the blocking mode for.
  blocking
    Whether to set the file to blocking mode.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = file.fileno()
  original = os.get_blocking(fd)
  os.set_blocking(fd, blocking)

  try:
    yield
  finally:
    os.set_blocking(fd, original)

@contextlib.contextmanager
def file_unbuffered(file: IO[bytes], /):
  """
  Set a file to unbuffered mode.

  The initial buffering mode is restored when exiting the context.

  Parameters
  ----------
  file
    The file to set to unbuffered mode.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = file.fileno()
  attr = termios.tcgetattr(fd)
  tty.setcbreak(fd, termios.TCSANOW)

  try:
    yield
  finally:
    termios.tcsetattr(fd, termios.TCSANOW, attr)


@contextlib.contextmanager
def watch_reader[**P](file: IO[bytes], /, callback: Callable[P, None], *args: P.args, **kwargs: P.kwargs):
  """
  Register a callback to be called when the file is readable.

  Parameters
  ----------
  file
    The file to monitor for readability.
  callback
    The callback to call when the file is readable.
  *args
    Positional arguments to pass to the callback.
  **kwargs
    Keyword arguments to pass to the callback.

  Returns
  -------
  AbstractContextManager[None]
  """

  loop = asyncio.get_running_loop()
  loop.add_reader(file, functools.partial(callback, *args, **kwargs))

  try:
    yield
  finally:
    loop.remove_reader(file)


@contextlib.contextmanager
def watch_writer[**P](file: IO[bytes], /, callback: Callable[P, None], *args: P.args, **kwargs: P.kwargs):
  """
  Register a callback to be called when the file is writable.

  Parameters
  ----------
  file
    The file to monitor for writability.
  callback
    The callback to call when the file is writable.
  *args
    Positional arguments to pass to the callback.
  **kwargs
    Keyword arguments to pass to the callback.

  Returns
  -------
  AbstractContextManager[None]
  """

  loop = asyncio.get_running_loop()
  loop.add_writer(file, functools.partial(callback, *args, **kwargs))

  try:
    yield
  finally:
    loop.remove_writer(file)


async def prompt(message: str, *, input: IO[bytes] = sys.stdin.buffer, output: IO[bytes] = sys.stdout.buffer):
  """
  Prompt the user for input.

  Parameters
  ----------
  message
    The prompt message to display.
  input
    The input file to read from.
  output
    The output file to write to.

  Returns
  -------
  str
    The user's input.
  """

  output.write(message.encode() + b'\n> ')
  output.flush()

  loop = asyncio.get_running_loop()
  future = loop.create_future()
  result = b''

  def callback():
    nonlocal result

    while True:
      char = input.read(1)

      if char is None:
        break

      if char == b'\x04':
        future.set_exception(EOFError())
        output.write(b'\n')
        break

      output.write(char)

      if char == b'\n':
        future.set_result(result.decode())
        break

      result += char

      output.flush()

  with (
      file_blocking(input, False),
      file_unbuffered(input),
      watch_reader(input, callback),
  ):
    return await future


__all__ = [
  'file_blocking',
  'file_unbuffered',
  'get_reader',
  'get_writer',
  'pipe',
  'prompt',
  'watch_reader',
  'watch_writer',
]
