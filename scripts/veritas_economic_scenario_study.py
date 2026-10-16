#!/usr/bin/env python3
"""Print the bounded synthetic Veritas capital-capacity sensitivity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from midas.veritas.scenario_study import build_report


def main() -> None:
    print(json.dumps(build_report(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
