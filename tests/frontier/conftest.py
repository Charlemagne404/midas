from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any

import pytest


_HELD_SOURCE_PATH_PARTS = ("data", "frontier", "live-" + "probes")


def _is_held_source_path(value: object) -> bool:
    try:
        path_value = os.fspath(value)
    except TypeError:
        return False
    if not isinstance(path_value, (str, bytes)):
        return False
    normalized = os.path.normpath(os.fsdecode(path_value))
    parts = Path(normalized).parts
    width = len(_HELD_SOURCE_PATH_PARTS)
    return any(parts[index : index + width] == _HELD_SOURCE_PATH_PARTS for index in range(len(parts)))


@pytest.fixture(autouse=True)
def deny_held_source_capture_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(path: object) -> None:
        if _is_held_source_path(path):
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
        deny(path)
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
