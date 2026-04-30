import asyncio
import os
import select
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process as AsyncioProcess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from os import PathLike
from signal import Signals
from typing import IO, Optional

from .cancel import ensure_correct_cancellation
from .thread_sync import to_thread


@dataclass(slots=True)
class ProcessTerminatedException(Exception):
  code: int

@dataclass(kw_only=True, slots=True)
class Process:
  """
  A class for managing a subprocess.
  """

  stdin: StreamWriter
  stdout: StreamReader
  stderr: StreamReader
  _proc: AsyncioProcess

  @property
  def pid(self):
    """
    The id of the process.
    """

    return self._proc.pid

  def send_signal(self, signal: Signals, /):
    """
    Send the specified signal to the process.

    Parameters
    ----------
    signal
      The signal to send.

    Raises
    ------
    ValueError
      If the process has already terminated.
    """

    if self._proc.returncode is not None:
      raise ValueError('Process has already terminated.')

    self._proc.send_signal(signal)

  async def try_wait(self):
    """
    Wait for the process to terminate.

    If a cancellation occurs, the function returns immediately without taking
    any action.

    Returns
    -------
    int
      The process return code.
    """

    return await self._proc.wait()

  async def wait(
    self,
    *,
    first_signal: Signals = Signals.SIGINT,
    subsequent_signals: Signals = Signals.SIGTERM,
  ):
    """
    Wait for the process to terminate.

    If a cancellation occurs, the specified signals are sent to the process
    until it terminates.

    Parameters
    ----------
    first_signal
      The signal to send to the process upon the first cancellation.
    subsequent_signals
      The signal to send to the process upon subsequent cancellations.

    Raises
    ------
    ProcessTerminatedException
      If the process terminates with a non-zero exit code.
    """

    with ensure_correct_cancellation():
      try:
        code = await self._proc.wait()
      except asyncio.CancelledError:
        self._proc.send_signal(first_signal)

        while True:
          try:
            code = await self._proc.wait()
          except asyncio.CancelledError:
            self._proc.send_signal(subsequent_signals)
          else:
            break

      if code != 0:
        raise ProcessTerminatedException(code)


type FileOp = Optional[IO | int]

async def start_process(
  command: Sequence[str] | str,
  *,
  cwd: Optional[PathLike | str] = None,
  env: Mapping[str, str] = {},
  stdin: FileOp = asyncio.subprocess.PIPE,
  stdout: FileOp = asyncio.subprocess.PIPE,
  stderr: FileOp = asyncio.subprocess.PIPE,
):
  """
  Start a process.

  The process is started in a new session.

  Parameters
  ----------
  command
    The command to execute. If a string is provided, it is executed through the
    shell.
  cwd
    The working directory of the process.
  env
    The environment variables of the process.
  stdin
    The operation for the standard input.
  stdout
    The operation for the standard output.
  stderr
    The operation for the standard error.

  Returns
  -------
  Process
    An object to manage the started process.
  """

  if isinstance(command, str):
    proc = await asyncio.create_subprocess_shell(
      command,
      env=env,
      stdin=stdin,
      stdout=stdout,
      stderr=stderr,
      start_new_session=True,
    )
  else:
    proc = await asyncio.create_subprocess_exec(
      command[0],
      *command[1:],
      cwd=cwd,
      env=env,
      stdin=stdin,
      stdout=stdout,
      stderr=stderr,
      start_new_session=True,
    )

  return Process(
    stdin=proc.stdin, # type: ignore
    stdout=proc.stdout, # type: ignore
    stderr=proc.stderr, # type: ignore
    _proc=proc,
  )


def process_exists(pid: int) -> bool:
  """
  Check if a process with the specified id exists.

  Parameters
  ----------
  pid
    The id of the process to check.

  Returns
  -------
  bool
    Whether a process with the specified id exists.
  """

  try:
    os.kill(pid, 0)
  except ProcessLookupError:
    return False
  except PermissionError:
    return True
  else:
    return True


async def reap_child_process(pid: int):
  """
  Wait for the child process with the specified id to terminate and return its
  exit code using os.waitpid().

  The process must not have been reaped yet and must not be reaped elsewhere
  while this function is running.

  Parameters
  ----------
  pid
    The id of the child process to wait for.

  Returns
  -------
  int
    The exit code of the child process.
  """

  if (await wait_for_process_kqueue(pid)) or (await wait_for_process_pidfd(pid)):
    _, status = os.waitpid(pid, 0)
  else:
    _, status = await to_thread(os.waitpid, pid, 0)

  return os.waitstatus_to_exitcode(status)


async def wait_for_process_kqueue(pid: int):
  if not hasattr(select, 'kqueue'):
    return False

  from .kqueue import KqueueEventManager

  loop = asyncio.get_running_loop()
  future = loop.create_future()

  if not process_exists(pid):
    return True

  def callback(kevent: select.kevent):
    future.set_result(None)

  async with KqueueEventManager(callback) as manager:
    if not process_exists(pid):
      return

    manager.update([
      select.kevent(
        pid,
        filter=select.KQ_FILTER_PROC,
        flags=(select.KQ_EV_ADD | select.KQ_EV_ONESHOT),
        fflags=select.KQ_NOTE_EXIT,
      ),
    ])

    await future

  return True

async def wait_for_process_pidfd(pid: int):
  if not hasattr(os, 'pidfd_open'):
    return False

  try:
    pidfd = os.pidfd_open(pid) # type: ignore
  except ProcessLookupError:
    return True
  except OSError:
    # Can be caused by insufficient permissions
    return False

  loop = asyncio.get_running_loop()
  future = loop.create_future()

  loop.add_reader(pidfd, future.set_result, None)

  try:
    await future
  finally:
    loop.remove_reader(pidfd)
    os.close(pidfd)

  return True

async def wait_for_process(pid: int):
  """
  Wait for the process with the specified id to terminate.

  If no process with the specified id exists, the function returns immediately.

  Parameters
  ----------
  pid
    The id of the process to wait for.
  """

  if await wait_for_process_kqueue(pid):
    return

  if await wait_for_process_pidfd(pid):
    return

  while process_exists(pid):
    await asyncio.sleep(0.1)



__all__ = [
  'Process',
  'ProcessTerminatedException',
  'reap_child_process',
  'start_process',
  'wait_for_process',
]
