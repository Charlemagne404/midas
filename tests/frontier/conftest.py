from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any

import pytest

_HELD_SOURCE_PATH_PARTS = ("data", "frontier", "live-" + "probes")


def _has_held_source_path_parts(path_value: str) -> bool:
    parts = Path(os.path.normpath(path_value)).parts
    width = len(_HELD_SOURCE_PATH_PARTS)
    return any(
        parts[index : index + width] == _HELD_SOURCE_PATH_PARTS for index in range(len(parts))
    )


def _is_held_source_path(value: object, *, dir_fd: int | None = None) -> bool:
    try:
        path_value = os.fspath(value)
    except TypeError:
        return False
    if not isinstance(path_value, (str, bytes)):
        return False
    path = os.fsdecode(path_value)
    if dir_fd is not None and not os.path.isabs(path):
        try:
            directory = os.readlink(f"/proc/self/fd/{dir_fd}")
        except (OSError, TypeError, ValueError):
            return True
        path = os.path.join(directory, path)
    try:
        return _has_held_source_path_parts(os.path.realpath(path))
    except (OSError, ValueError):
        return True


@pytest.fixture(autouse=True)
def deny_held_source_capture_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(path: object, *, dir_fd: int | None = None) -> None:
        if _is_held_source_path(path, dir_fd=dir_fd):
            raise PermissionError("Frontier tests may not access held source captures")

    original_builtin_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open

    def guarded_builtin_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        deny(file)
        return original_builtin_open(file, *args, **kwargs)

    def guarded_io_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        deny(file)
        return original_io_open(file, *args, **kwargs)

    def guarded_os_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        deny(path, dir_fd=kwargs.get("dir_fd"))
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
