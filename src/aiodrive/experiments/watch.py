import asyncio
import os
import select
import signal
from asyncio import Future
from collections.abc import Callable
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

from ..modules.signals import SignalHandledException, handle_signal
from .selector_event import KqueueEventManager


type PathParts = tuple[str, ...]

@dataclass(slots=True)
class Entry:
  fd: int
  parts: PathParts

@dataclass(slots=True)
class DirectoryEntry(Entry):
  children: set[str] = field(default_factory=set)

@dataclass(slots=True)
class FileEntry(Entry):
  pass


async def watch_files(raw_path: PathLike | str, callback: Callable, /):
  loop = asyncio.get_running_loop()
  target_path = Path(raw_path).resolve()

  entries_by_fd = dict[int, Entry]()
  entries_by_parts = dict[PathParts, Entry]()


  def add_path(source_parts: PathParts, is_source_dir: bool):
    queue = list()
    queue.append((source_parts, is_source_dir))

    while queue:
      old_queue = queue
      queue = []

      kevs = list[select.kevent]()

      for parts, is_dir in old_queue:
        try:
          fd = os.open(target_path / '/'.join(parts), os.O_RDONLY)
        except FileNotFoundError:
          continue

        if is_dir:
          entry = DirectoryEntry(fd, parts)
        else:
          entry = FileEntry(fd, parts)

        entries_by_fd[fd] = entry
        entries_by_parts[parts] = entry

        if parts:
          *parent_parts, name = parts
          parent_entry = entries_by_parts[tuple(parent_parts)]

          assert isinstance(parent_entry, DirectoryEntry)
          parent_entry.children.add(name)

        loop.call_soon(callback, 'create', entry.parts)

        kevs.append(
          select.kevent(
              fd,
              filter=select.KQ_FILTER_VNODE,
              flags=(select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
              fflags=(select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME | select.KQ_NOTE_WRITE),
          ),
        )

      # manager.update(kevs)
      # print(f"Registered {len(kevs)} kevents")

      manager.update(kevs)

      for parts, is_dir in old_queue:
        if is_dir:
          try:
            for dir_entry in os.scandir(target_path / '/'.join(parts)):
              queue.append((
                (*parts, dir_entry.name),
                dir_entry.is_dir(),
              ))

              entry = entries_by_parts[parts]

              assert isinstance(entry, DirectoryEntry)
              entry.children.add(dir_entry.name)
          except NotADirectoryError:
            pass


  def kqueue_callback(kqueue_event: select.kevent):
    entry = entries_by_fd[kqueue_event.ident]

    if (kqueue_event.fflags & select.KQ_NOTE_WRITE) > 0:
      match entry:
        case FileEntry():
          loop.call_soon(callback, 'write', entry.parts)
        case DirectoryEntry():
          dir_entries = {
            dir_entry.name: dir_entry for dir_entry in os.scandir(target_path / '/'.join(entry.parts))
          }

          children = set(dir_entries.keys())

          for name in children - entry.children:
            add_path((*entry.parts, name), dir_entries[name].is_dir())

    if (kqueue_event.fflags & select.KQ_NOTE_DELETE) > 0:
      search_queue = [entry]
      targets = list[Entry]()

      while search_queue:
        search_entry = search_queue.pop()
        targets.append(search_entry)

        if isinstance(search_entry, DirectoryEntry):
          for child_name in search_entry.children:
            search_queue.append(entries_by_parts[(*search_entry.parts, child_name)])

      for target in reversed(targets):
        loop.call_soon(callback, 'delete', target)

        if target.parts:
          *parent_parts, name = target.parts
          parent_entry = entries_by_parts[tuple(parent_parts)]

          assert isinstance(parent_entry, DirectoryEntry)
          parent_entry.children.remove(name)

        del entries_by_fd[target.fd]
        del entries_by_parts[target.parts]

        os.close(target.fd)


  async with KqueueEventManager(kqueue_callback) as manager:
    add_path((), True)

    await Future()


if __name__ == "__main__":
  async def main():
    try:
      with handle_signal(signal.SIGINT):
        await watch_files('playground', print)
    except SignalHandledException:
      print("Received SIGINT")

  asyncio.run(main())
