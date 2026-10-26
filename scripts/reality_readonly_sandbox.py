"""Apply a per-worker Landlock policy: filesystem reads everywhere, writes only in staging."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path

LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38

FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
FS_REMOVE_DIR = 1 << 4
FS_REMOVE_FILE = 1 << 5
FS_MAKE_CHAR = 1 << 6
FS_MAKE_DIR = 1 << 7
FS_MAKE_REG = 1 << 8
FS_MAKE_SOCK = 1 << 9
FS_MAKE_FIFO = 1 << 10
FS_MAKE_BLOCK = 1 << 11
FS_MAKE_SYM = 1 << 12
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14

ALL_FILESYSTEM_ACCESS = (1 << 15) - 1
READ_ONLY_ACCESS = FS_READ_FILE | FS_READ_DIR
STAGING_ACCESS = ALL_FILESYSTEM_ACCESS
LANDLOCK_CREATE_RULESET_SYSCALL = 444
LANDLOCK_ADD_RULE_SYSCALL = 445
LANDLOCK_RESTRICT_SELF_SYSCALL = 446


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _check_syscall(result: int, operation: str) -> int:
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, f"Landlock {operation}: {os.strerror(error)}")
    return result


def apply_readonly_source_policy(source_root: Path, writable_root: Path) -> dict[str, object]:
    """Deny filesystem mutation except below writable_root for this process tree.

    The rule grants read access across the filesystem and all filesystem rights
    only below the run-owned staging root. Rules follow symlinks to their resolved
    targets, so a view symlink into the production archive stays read-only.
    """
    if platform.system() != "Linux":
        raise RuntimeError("Full-store recovery requires Linux Landlock isolation")
    source_root = source_root.resolve(strict=True)
    writable_root = writable_root.resolve(strict=True)
    if not source_root.is_dir() or not writable_root.is_dir():
        raise ValueError("Landlock roots must be existing directories")
    if source_root == writable_root or source_root.is_relative_to(writable_root) or writable_root.is_relative_to(source_root):
        raise ValueError("Source and writable staging roots must be disjoint")

    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = _check_syscall(
        libc.syscall(
            ctypes.c_long(LANDLOCK_CREATE_RULESET_SYSCALL),
            ctypes.c_void_p(0),
            ctypes.c_size_t(0),
            ctypes.c_uint(LANDLOCK_CREATE_RULESET_VERSION),
        ),
        "ABI query",
    )
    if abi < 3:
        raise RuntimeError(f"Landlock ABI {abi} lacks the required filesystem rights")

    attributes = _RulesetAttr(handled_access_fs=ALL_FILESYSTEM_ACCESS, handled_access_net=0)
    ruleset_fd = _check_syscall(
        libc.syscall(
            ctypes.c_long(LANDLOCK_CREATE_RULESET_SYSCALL),
            ctypes.byref(attributes),
            ctypes.c_size_t(ctypes.sizeof(attributes)),
            ctypes.c_uint(0),
        ),
        "ruleset creation",
    )
    path_fds: list[int] = []
    try:
        for path, access in ((Path("/"), READ_ONLY_ACCESS), (writable_root, STAGING_ACCESS)):
            path_fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            path_fds.append(path_fd)
            rule = _PathBeneathAttr(allowed_access=access, parent_fd=path_fd)
            _check_syscall(
                libc.syscall(
                    ctypes.c_long(LANDLOCK_ADD_RULE_SYSCALL),
                    ctypes.c_int(ruleset_fd),
                    ctypes.c_int(LANDLOCK_RULE_PATH_BENEATH),
                    ctypes.byref(rule),
                    ctypes.c_uint(0),
                ),
                "path rule",
            )

        _check_syscall(
            libc.prctl(
                ctypes.c_int(PR_SET_NO_NEW_PRIVS),
                ctypes.c_ulong(1),
                ctypes.c_ulong(0),
                ctypes.c_ulong(0),
                ctypes.c_ulong(0),
            ),
            "no_new_privs",
        )
        _check_syscall(
            libc.syscall(
                ctypes.c_long(LANDLOCK_RESTRICT_SELF_SYSCALL),
                ctypes.c_int(ruleset_fd),
                ctypes.c_uint(0),
            ),
            "policy activation",
        )
    finally:
        for path_fd in path_fds:
            os.close(path_fd)
        os.close(ruleset_fd)

    return {
        "mechanism": "Landlock filesystem ruleset",
        "abi": abi,
        "source_root": str(source_root),
        "staging_root": str(writable_root),
        "filesystem_mutation": "denied except below staging_root",
        "source_reads": "allowed",
        "symlink_targets": "subject to resolved target rules",
        "chmod_and_other_unhandled_metadata_operations": "not restricted by Landlock; candidate worker performs none",
    }


def verify_source_write_denied(source_file: Path) -> None:
    """Prove the active policy blocks a write open without changing source bytes."""
    try:
        descriptor = os.open(source_file, os.O_WRONLY)
    except PermissionError:
        return
    except OSError as error:
        if error.errno in (1, 13, 30):
            return
        raise
    else:
        os.close(descriptor)
        raise RuntimeError("Landlock policy allowed a write open on a source file")
