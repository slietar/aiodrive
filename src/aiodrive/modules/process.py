import asyncio
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process as AsyncioProcess
from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
from signal import Signals
from typing import Optional

from .cancel import ensure_correct_cancellation


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


async def start_process(
  command: Sequence[str] | str,
  *,
  cwd: Optional[PathLike | str] = None,
  env: dict[str, str] = {},
):
  """
  Start a process.

  Parameters
  ----------
  command
    The command to execute. If a string is provided, it is executed through the
    shell.
  cwd
    The working directory of the process.
  env
    The environment variables of the process.

  Returns
  -------
  Process
    An object to manage the started process.
  """

  if isinstance(command, str):
    proc = await asyncio.create_subprocess_shell(
      command,
      env=env,
      stdin=asyncio.subprocess.PIPE,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE,
    )
  else:
    proc = await asyncio.create_subprocess_exec(
      command[0],
      *command[1:],
      cwd=cwd,
      env=env,
      stdin=asyncio.subprocess.PIPE,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE,
    )

  assert proc.stdin is not None
  assert proc.stdout is not None
  assert proc.stderr is not None

  return Process(
    stdin=proc.stdin,
    stdout=proc.stdout,
    stderr=proc.stderr,
    _proc=proc,
  )


__all__ = [
  'Process',
  'ProcessTerminatedException',
  'start_process',
]
