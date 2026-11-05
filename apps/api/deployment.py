"""Runtime deployment identity helpers."""

import hashlib
import json

from apps.api.config import Settings


def configuration_identity(settings: Settings) -> str:
    """Return a stable fingerprint without exposing configuration values."""
    payload = json.dumps(
        settings.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
