import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path, PurePath
import select


class DoubleDict[ForwardKey, ForwardValue]:
  def __init__(self):
    self.forward = dict[ForwardKey, ForwardValue]()
    self.backward = dict[ForwardValue, ForwardKey]()

  def __setitem__(self, key: ForwardKey, value: ForwardValue):
    self.forward[key] = value
    self.backward[value] = key


@dataclass(slots=True)
class FileEntry:
  fd: int

class DirEntry:
  fd: int
  children: list[str]

type PathParts = tuple[str, ...]

async def watch_files(raw_path: PathLike | str, callback: Callable, /):
  target_path = Path(raw_path).resolve()
  entries = DoubleDict[str, int]()

  queue = []
  queue.append(('.', True))

  while queue:
    old_queue = queue
    queue = []

    kevs = list[select.kevent]()

    for rel_path, is_dir in old_queue:
      try:
        fd = os.open(target_path / rel_path, os.O_RDONLY | (os.O_DIRECTORY if is_dir else 0))
      except (FileNotFoundError, NotADirectoryError): # Why??
        continue

      entries[rel_path] = fd

      kevs.append(
        select.kevent(
            fd,
            filter=select.KQ_FILTER_VNODE,
            flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
            fflags=(select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME | select.KQ_NOTE_WRITE),
        ),
      )

    manager.update(kevs)

    for rel_path, is_dir in old_queue:
      if is_dir:
        for entry in os.scandir(target_path / rel_path):
          queue.append((
            str(PurePath(rel_path) / entry.name),
            entry.is_dir(),
          ))

    # fds = []

    # for entry in os.scandir(target_path / rel_path):
    #   fd = os.open(target_path / rel_path, os.O_RDONLY)

    #   if entry.is_dir():
    #     queue.append(entry.path)


async def main():
  def func():
    pass

  await watch_files('w', func)


asyncio.run(main())
