"""Copy the committed public Polymarket capture into an isolated browser root."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from tempfile import gettempdir

CAPTURE_STORE_SHA256 = "b0576bf2008248f9567144a2bcffd0f86b3de71d0a067beb389ec9b1e7cfe35b"
CAPTURE_RELATIVE_PATH = Path(
    "data/frontier-live-evidence-polymarket-20261028T170445Z/research-store/frontier.sqlite3"
)
SEED_MARKER = ".frontier-captured-e2e-seed"


def seed_store(root: Path) -> None:
    if root.is_symlink():
        raise RuntimeError("Refusing to seed a symlinked Frontier root")
    browser_root = root.parent.resolve()
    temporary_root = Path(gettempdir()).resolve()
    if browser_root.parent != temporary_root or not browser_root.name.startswith("midas-browser-"):
        raise RuntimeError("Captured evidence requires a fresh isolated temporary browser root")
    run_id = os.environ.get("MIDAS_FRONTIER_E2E_RUN_ID")
    if not run_id:
        raise RuntimeError("Captured evidence requires a Playwright run owner identity")
    owner_marker = browser_root / ".midas-frontier-e2e-owner"
    if owner_marker.is_symlink() or not owner_marker.is_file():
        raise RuntimeError("Captured evidence browser root has no regular owner marker")
    expected_owner = f"{run_id}\n{browser_root.resolve()}\n"
    if owner_marker.read_text(encoding="utf-8") != expected_owner:
        raise RuntimeError("Captured evidence browser root belongs to a different Playwright run")

    seed_marker = browser_root / SEED_MARKER
    expected_seed = f"{run_id}\n{CAPTURE_STORE_SHA256}\n3\n10\n"
    if root.exists():
        destination = root / "frontier.sqlite3"
        if (
            root.is_symlink()
            or not root.is_dir()
            or destination.is_symlink()
            or not destination.is_file()
            or seed_marker.is_symlink()
            or not seed_marker.is_file()
            or seed_marker.read_text(encoding="utf-8") != expected_seed
        ):
            raise RuntimeError(f"Refusing to reuse an unverified captured Frontier root: {root}")
        print("Reusing this Playwright run's pinned public Polymarket capture")
        return
    if seed_marker.exists() or seed_marker.is_symlink():
        raise RuntimeError("Captured evidence seed marker exists without its Frontier store")

    repository = Path(__file__).resolve().parents[3]
    source = repository / CAPTURE_RELATIVE_PATH
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Committed Polymarket evidence store is missing or not a regular file")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != CAPTURE_STORE_SHA256:
        raise RuntimeError("Committed Polymarket evidence store hash differs from the E2E pin")

    root.mkdir(parents=True)
    destination = root / "frontier.sqlite3"
    destination.write_bytes(source.read_bytes())
    if hashlib.sha256(destination.read_bytes()).hexdigest() != CAPTURE_STORE_SHA256:
        raise RuntimeError("Copied Polymarket evidence store failed its hash check")

    with sqlite3.connect(f"file:{destination.as_posix()}?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        observations = int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        relationships = int(connection.execute("SELECT COUNT(*) FROM relationships").fetchone()[0])
    if integrity != ("ok",) or observations != 3 or relationships != 10:
        raise RuntimeError("Captured Polymarket store failed read-only integrity/count checks")

    with seed_marker.open("x", encoding="utf-8") as marker_file:
        marker_file.write(expected_seed)

    print(
        f"Copied hash-verified public Polymarket evidence into {destination}; "
        f"observations={observations}, relationships={relationships}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: seed_captured_frontier_store.py FRONTIER_ROOT")
    seed_store(Path(sys.argv[1]))
