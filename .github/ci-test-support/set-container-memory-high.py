#!/usr/bin/env python3
"""Set memory.high on one uniquely identified disposable Docker cgroup."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--memory-high", type=int, required=True)
    parser.add_argument("--memory-max", type=int, required=True)
    args = parser.parse_args()
    if args.pid <= 0 or not args.container_id or args.memory_high <= 0:
        parser.error("pid, container id, and memory.high must identify a valid test scope")

    memberships = Path(f"/proc/{args.pid}/cgroup").read_text(encoding="ascii").splitlines()
    relative = next((line.split(":", 2)[2] for line in memberships if line.startswith("0::")), None)
    if not relative or not relative.startswith("/") or ".." in Path(relative).parts:
        raise SystemExit("test container has no safe cgroup v2 membership")
    if not any(args.container_id in part for part in Path(relative).parts):
        raise SystemExit("refusing to modify a cgroup not uniquely owned by this container")

    cgroup_root = Path("/sys/fs/cgroup").resolve()
    group = cgroup_root / relative.lstrip("/")
    if group.is_symlink() or not group.is_dir() or not group.resolve().is_relative_to(cgroup_root):
        raise SystemExit("test container cgroup escaped the cgroup hierarchy")
    maximum = (group / "memory.max").read_text(encoding="ascii").strip()
    swap = (group / "memory.swap.max").read_text(encoding="ascii").strip()
    if maximum != str(args.memory_max) or swap != "0":
        raise SystemExit(f"unexpected test cgroup limits: max={maximum} swap={swap}")
    current = int((group / "memory.current").read_text(encoding="ascii").strip())
    if current >= args.memory_high:
        raise SystemExit("test container is already at its requested memory.high")

    target = group / "memory.high"
    if target.is_symlink():
        raise SystemExit("test cgroup memory.high is a symlink")
    descriptor = os.open(target, os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(str(args.memory_high))
    actual = target.read_text(encoding="ascii").strip()
    if actual != str(args.memory_high):
        raise SystemExit(f"failed to establish memory.high={args.memory_high}: got {actual}")
    print(
        "Bounded disposable cgroup: "
        f"memory.high={actual} memory.max={maximum} memory.swap.max={swap}"
    )


if __name__ == "__main__":
    main()
