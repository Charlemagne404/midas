"""Operational CLI with no HTTP listener."""

import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path

from .collector import run
from .config import Config
from .replay import replay
from .storage import atomic_json, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Reality public read-only recorder")
    parser.add_argument("command", choices=["record", "status", "export", "replay"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--through", type=int)
    args = parser.parse_args()
    config = Config.load(args.config) if args.config else Config()
    root = Path(config.root)
    if args.command == "record":
        asyncio.run(run(config, args.duration))
    elif args.command == "status":
        status = json.loads((root / "status.json").read_text())
        age = (time.time_ns() - status["updated_ns"]) / 1e9
        status["status_age_seconds"] = age
        if age > 10:
            status["state"] = "STATUS_STALE"
        print(json.dumps(status, indent=2))
    elif args.command == "export":
        if args.output is None:
            parser.error("export requires --output (new directory)")
        value = manifest(root)
        replay(root, value)  # validate integrity before copying
        args.output.mkdir(parents=True, exist_ok=False)
        for segment in value["segments"]:
            shutil.copy2(root / segment["file"], args.output / segment["file"])
        atomic_json(args.output / "manifest.json", value)
        print(json.dumps(value, indent=2))
    else:
        value = json.loads(args.manifest.read_text()) if args.manifest else manifest(root)
        source = args.manifest.parent if args.manifest else root
        engine, checkpoints = replay(source, value, args.through)
        result = dict(
            state_sha256=engine.digest(), checkpoints_verified=checkpoints, **engine.state()
        )
        if args.output:
            atomic_json(args.output, result)
        print(json.dumps({k: v for k, v in result.items() if k != "books"}, indent=2))


if __name__ == "__main__":
    main()
