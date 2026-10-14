"""Persisted bounded recorder configuration."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Config:
    root: str = "/home/charlie/midas-reality/data/recordings/reality"
    markets: int = 3
    discovery_limit: int = 50
    refresh_seconds: float = 600
    resync_seconds: float = 300
    stale_seconds: float = 60
    queue_size: int = 32
    budget_bytes: int = 2 * 1024**3
    reserve_bytes: int = 5 * 1024**3
    segment_bytes: int = 8 * 1024**2
    segment_seconds: float = 300
    retention_days: int = 30  # stop at the budget; never prune original observations
    selection_mode: str = "legacy"
    selection_seed: int = 20261014
    near_expiry_tag_id: int = 2  # verified Politics tag; unfiltered expiry page is also retained
    comparison_seconds: float = 0  # opt-in; no network work added to legacy fixtures
    comparison_timeout_seconds: float = 5

    def __post_init__(self) -> None:
        for name in (
            "refresh_seconds",
            "resync_seconds",
            "stale_seconds",
            "segment_seconds",
            "comparison_seconds",
            "comparison_timeout_seconds",
        ):
            if not math.isfinite(getattr(self, name)):
                raise ValueError("Timing values must be finite")
        if not isinstance(self.near_expiry_tag_id, int) or self.near_expiry_tag_id < 1:
            raise ValueError("Near-expiry tag ID must be positive")
        if self.selection_mode not in {"legacy", "stratified-v1"}:
            raise ValueError("Unsupported selection mode")
        if self.comparison_seconds != 0 and self.comparison_seconds < 10:
            raise ValueError("Independent comparison interval must be >=10 seconds")
        if not 1 <= self.comparison_timeout_seconds <= 10:
            raise ValueError("Comparison timeout must be 1..10 seconds")
        if not isinstance(self.selection_seed, int) or not 0 <= self.selection_seed < 2**32:
            raise ValueError("Selection seed must be uint32")
        if not 1 <= self.markets <= 10 or not self.markets <= self.discovery_limit <= 200:
            raise ValueError("Cohort must contain 1..10 markets, discovery <=200")
        if (
            not 10 <= self.queue_size <= 64
            or min(self.refresh_seconds, self.resync_seconds, self.stale_seconds) < 10
        ):
            raise ValueError("Unsafe queue or refresh configuration")
        if (
            min(
                self.budget_bytes,
                self.reserve_bytes,
                self.segment_bytes,
                self.segment_seconds,
                self.retention_days,
            )
            <= 0
        ):
            raise ValueError("Storage limits must be positive")
        root = Path(self.root).resolve()
        workspace = Path(__file__).resolve().parents[3]
        if not root.is_relative_to(workspace / "data" / "recordings"):
            raise ValueError("Reality storage must be inside this worktree data/recordings")

    @classmethod
    def load(cls, path: Path) -> "Config":
        return cls(**json.loads(path.read_text()))

    def dump(self) -> dict[str, Any]:
        return asdict(self)
