import contextlib
import os
import termios
import tty
from typing import IO, Protocol


class FileDescriptorLikeFile(Protocol):
  def fileno(self) -> int:
    ...

type FileDescriptorLike = FileDescriptorLikeFile | int

def get_fd_from_file(file: FileDescriptorLike, /) -> int:
  if isinstance(file, int):
    return file

  return file.fileno()


@contextlib.contextmanager
def set_file_blocking(fd_like: IO[bytes], /, blocking: bool):
  """
  Set the blocking mode of a file.

  The initial blocking mode is restored when exiting the context.

  Parameters
  ----------
  fd_like
    The file to set the blocking mode for.
  blocking
    Whether to set the file to blocking mode.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = get_fd_from_file(fd_like)
  original = os.get_blocking(fd)
  os.set_blocking(fd, blocking)

  try:
    yield
  finally:
    os.set_blocking(fd, original)


@contextlib.contextmanager
def set_file_rawmode(fd_like: FileDescriptorLike):
  """
  Set a file to raw mode.

  The initial mode is restored when exiting the context.

  Parameters
  ----------
  fd_like
    The file to set to raw mode.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = get_fd_from_file(fd_like)
  original_attr = termios.tcgetattr(fd)
  tty.setraw(fd)

  try:
    yield
  finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, original_attr)

@contextlib.contextmanager
def set_file_attribute(fd_like: FileDescriptorLike, attr: termios._Attr, *, when: int = termios.TCSADRAIN):
  """
  Set arbitrary termios attributes on a file descriptor.

  The initial attributes are restored when exiting the context.

  Parameters
  ----------
  fd_like
    The file to set attributes for.
  attr
    The termios attribute list to set.
  when
    When to apply the attribute change.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = get_fd_from_file(fd_like)
  original_attr = termios.tcgetattr(fd)
  termios.tcsetattr(fd, when, attr)

  try:
    yield
  finally:
    termios.tcsetattr(fd, when, original_attr)

@contextlib.contextmanager
def set_file_unbuffered(fd_like: FileDescriptorLike, /):
  """
  Set a file to unbuffered mode.

  The initial buffering mode is restored when exiting the context.

  Parameters
  ----------
  fd_like
    The file to set to unbuffered mode.

  Returns
  -------
  AbstractContextManager[None]
  """

  fd = get_fd_from_file(fd_like)
  original_attr = termios.tcgetattr(fd)
  tty.setcbreak(fd, termios.TCSADRAIN)

  try:
    yield
  finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, original_attr)


__all__ = [
  'set_file_attribute',
  'set_file_blocking',
  'set_file_rawmode',
  'set_file_unbuffered',
]
