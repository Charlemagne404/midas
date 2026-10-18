"""Event-driven logical artifact sizes, with conservative full-scan fallback."""

import ctypes
import errno
import os
import stat
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

MODIFY = 0x00000002
ATTRIB = 0x00000004
CLOSE_WRITE = 0x00000008
MOVED_FROM = 0x00000040
MOVED_TO = 0x00000080
CREATE = 0x00000100
DELETE = 0x00000200
DELETE_SELF = 0x00000400
MOVE_SELF = 0x00000800
UNMOUNT = 0x00002000
OVERFLOW = 0x00004000
IGNORED = 0x00008000
MASK = (
    MODIFY
    | ATTRIB
    | CLOSE_WRITE
    | MOVED_FROM
    | MOVED_TO
    | CREATE
    | DELETE
    | DELETE_SELF
    | MOVE_SELF
)
RESET = DELETE_SELF | MOVE_SELF | UNMOUNT | OVERFLOW | IGNORED
EVENT = struct.Struct("iIII")
# Historical Arena trees can contain far more files than the per-user inotify
# watch limit. Watching all of those immutable files is unnecessary: Arena
# publishers create or atomically replace artifacts while holding worker.lock,
# and their parent-directory events are sufficient to account for that growth.
# Keep file watches for small trees and for files created/replaced during a job.
MAX_INITIAL_FILE_WATCHES = 8192


class UsageIndex:
    """Count bytes per path, including hard links and symlink-file targets.

    Directory symlinks are never traversed. Symlink targets are restatted on each
    observation; every regular inode receives a watch, including files that gain
    external hard links later. Watch failure,
    queue overflow or topology ambiguity discards the cache and reconciles.
    """

    def __init__(self, root: Path, fallback: Callable[[Path], tuple[int, int]]):
        self.root = root.absolute()
        self.fallback = fallback
        self.fd = -1
        self.lib: Any = None
        self.watches: dict[int, Path] = {}
        self.watch_inodes: dict[int, tuple[int, int]] = {}
        self.watched_inodes: set[tuple[int, int]] = set()
        self.directories: set[Path] = set()
        self.poll_files: set[Path] = set()
        self.files: dict[Path, tuple[int, tuple[int, int]]] = {}
        self.aliases: dict[tuple[int, int], set[Path]] = {}
        self.links: set[Path] = set()
        self.total = 0
        self.root_identity: tuple[int, int] | None = None
        self.reconciliations = 0
        self.fallbacks = 0
        self.last_error: str | None = None
        self.file_watch_mode = "UNINITIALIZED"
        self._rebuild()

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def _watch(self, path: Path, inode: tuple[int, int] | None = None) -> None:
        wd = self.lib.inotify_add_watch(self.fd, os.fsencode(path), MASK)
        if wd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(path))
        self.watches[wd] = path
        if inode is not None:
            self.watch_inodes[wd] = inode
            self.watched_inodes.add(inode)

    def _forget(self, path: Path) -> None:
        self.links.discard(path)
        self.poll_files.discard(path)
        old = self.files.pop(path, None)
        if old:
            self.total -= old[0]
            self.aliases[old[1]].discard(path)
            if not self.aliases[old[1]]:
                del self.aliases[old[1]]

    def _remember(self, path: Path, info: os.stat_result) -> None:
        old = self.files.get(path)
        inode = (info.st_dev, info.st_ino)
        if old and old[1] != inode:
            linked = path in self.links
            self._forget(path)
            if linked:
                self.links.add(path)
            old = None
        self.total += info.st_size - (old[0] if old else 0)
        self.files[path] = (info.st_size, inode)
        self.aliases.setdefault(inode, set()).add(path)

    def _refresh(self, path: Path, watch_file: bool = True) -> None:
        try:
            own = path.lstat()
        except FileNotFoundError:
            self._forget(path)
            return
        if stat.S_ISDIR(own.st_mode):
            if path not in self.directories:
                self._scan(path, watch_files=True)
            return
        if stat.S_ISLNK(own.st_mode):
            self.links.add(path)
        else:
            self.links.discard(path)
        try:
            info = path.stat()
        except FileNotFoundError:
            self._forget(path)
            if stat.S_ISLNK(own.st_mode):
                self.links.add(path)
            return
        if not stat.S_ISREG(info.st_mode):
            self._forget(path)
            if stat.S_ISLNK(own.st_mode):
                self.links.add(path)
            return
        inode = (info.st_dev, info.st_ino)
        if watch_file and self.file_watch_mode == "DIRECTORY_EVENTS":
            # The historical tree already selected directory-only mode. New
            # paths are tracked by the parent directory and polled individually
            # so in-place writes remain visible without repeatedly asking the
            # exhausted per-user watch table for another inode watch.
            self.poll_files.add(path)
        elif watch_file and inode not in self.watched_inodes:
            try:
                descriptor = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except FileNotFoundError:
                self._forget(path)
                return
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise OSError("Artifact type changed during watch registration")
                inode = (info.st_dev, info.st_ino)
                try:
                    # Watch the opened inode, not a pathname that another process
                    # could replace between stat() and watch registration.
                    self._watch(Path(f"/proc/self/fd/{descriptor}"), inode)
                    self.poll_files.discard(path)
                except OSError as error:
                    if error.errno != errno.ENOSPC:
                        raise
                    # The directory watch still accounts for atomic creates and
                    # replacements. Poll only this newly active path so a write
                    # in place remains visible without rescanning Arena history.
                    self.poll_files.add(path)
                    self.last_error = str(error)
                info = os.fstat(descriptor)
                try:
                    current = path.stat()
                except FileNotFoundError as error:
                    raise OSError("Artifact vanished during watch registration") from error
                if (current.st_dev, current.st_ino) != inode:
                    raise OSError("Artifact replaced during watch registration")
            finally:
                os.close(descriptor)
        peers = set(self.aliases.get(inode, ()))
        self._remember(path, info)
        for peer in peers - {path}:
            try:
                current = peer.stat()
            except FileNotFoundError:
                self._forget(peer)
                continue
            if stat.S_ISREG(current.st_mode):
                self._remember(peer, current)
            else:
                self._forget(peer)

    def _scan(self, root: Path, watch_files: bool = True) -> None:
        pending = [root]
        while pending:
            directory = pending.pop()
            try:
                # Install before enumeration so concurrent publications enqueue
                # events even if they race the initial directory scan.
                self._watch(directory)
                self.directories.add(directory)
                with os.scandir(directory) as entries:
                    for entry in entries:
                        path = Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(path)
                        else:
                            self._refresh(path, watch_file=watch_files)
            except FileNotFoundError:
                continue

    def _rebuild(self) -> None:
        self.close()
        self.watches.clear()
        self.watch_inodes.clear()
        self.watched_inodes.clear()
        self.directories.clear()
        self.poll_files.clear()
        self.files.clear()
        self.aliases.clear()
        self.links.clear()
        self.total = 0
        self.file_watch_mode = "FULL_SCAN_FALLBACK"
        self.reconciliations += 1
        try:
            if not self.root.is_dir():
                raise FileNotFoundError("Artifact root is not an existing directory")
            info = self.root.stat()
            self.root_identity = (info.st_dev, info.st_ino)
            self.lib = ctypes.CDLL(None, use_errno=True)
            self.lib.inotify_init1.argtypes = [ctypes.c_int]
            self.lib.inotify_init1.restype = ctypes.c_int
            self.lib.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
            self.lib.inotify_add_watch.restype = ctypes.c_int
            self.fd = self.lib.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
            if self.fd < 0:
                raise OSError(ctypes.get_errno(), "inotify initialization failed")
            # Build the exact initial size cache while watching directories only.
            # If the historical tree is small enough, add the stronger inode
            # watches used by the original index. Large trees remain exact for
            # Arena's atomic artifact publishers and avoid exhausting inotify.
            self._scan(self.root, watch_files=False)
            if len(self.files) <= MAX_INITIAL_FILE_WATCHES:
                self.file_watch_mode = "ALL_INITIAL_FILES"
                for path in list(self.files):
                    self._refresh(path, watch_file=True)
            else:
                self.file_watch_mode = "DIRECTORY_EVENTS"
        except (AttributeError, OSError) as error:
            self.last_error = str(error)
            self.file_watch_mode = "FULL_SCAN_FALLBACK"
            self.close()

    def _events(self) -> set[Path] | None:
        dirty: set[Path] = set()
        for _ in range(256):
            try:
                payload = os.read(self.fd, 65536)
            except BlockingIOError:
                return dirty
            if not payload:
                raise OSError("Artifact notification stream closed")
            offset = 0
            while offset < len(payload):
                wd, mask, _, length = EVENT.unpack_from(payload, offset)
                name = payload[offset + EVENT.size : offset + EVENT.size + length].split(b"\0", 1)[
                    0
                ]
                offset += EVENT.size + length
                if mask & (UNMOUNT | OVERFLOW):
                    return None
                inode = self.watch_inodes.get(wd)
                if inode is not None:
                    dirty.update(self.aliases.get(inode, ()))
                    if mask & IGNORED:
                        self.watch_inodes.pop(wd, None)
                        self.watched_inodes.discard(inode)
                        self.watches.pop(wd, None)
                    continue
                if mask & RESET:
                    return None
                base = self.watches.get(wd)
                if base is None:
                    return None
                dirty.add(base / os.fsdecode(name) if name else base)
        return None

    def usage(self) -> tuple[int, int]:
        if self.fd >= 0:
            try:
                info = self.root.stat()
                if (info.st_dev, info.st_ino) != self.root_identity:
                    self._rebuild()
            except FileNotFoundError:
                self._rebuild()
        if self.fd < 0:
            self.fallbacks += 1
            return self.fallback(self.root)
        try:
            for _ in range(8):
                dirty = self._events()
                if dirty is None:
                    self._rebuild()
                    if self.fd < 0:
                        break
                    continue
                for path in dirty | set(self.links) | set(self.poll_files):
                    self._refresh(path)
                if not dirty:
                    return self.total, len(self.files)
            # Sustained writes or repeated watch invalidations cannot return an
            # assumed cached total. Reconcile with the existing exact scanner.
            self._rebuild()
            self.fallbacks += 1
            return self.fallback(self.root)
        except (OSError, ValueError, struct.error) as error:
            self.last_error = str(error)
            self.close()
            self.fallbacks += 1
            return self.fallback(self.root)
