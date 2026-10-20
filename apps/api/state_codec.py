"""Versioned physical account encoding; logical state and journal hashes are unchanged."""

import base64
import binascii
import json
import zlib
from typing import Any

MARKER = "__midas_paper_state_codec__"
VERSION = "zlib-json-1"
MAX_STATE_BYTES = 64 * 1024**2
MIN_STATE_BYTES = 4096


def encode_state(value: dict[str, Any]) -> dict[str, Any]:
    if MARKER in value:
        raise ValueError("Paper state encoding marker is reserved")
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) < MIN_STATE_BYTES or len(raw) > MAX_STATE_BYTES:
        return value
    compressed = base64.b64encode(zlib.compress(raw, 1)).decode("ascii")
    envelope = {MARKER: VERSION, "plain_bytes": len(raw), "data": compressed}
    # Small/incompressible states keep their existing plain representation.
    return envelope if len(compressed) + 128 < len(raw) * 0.9 else value


def decode_state(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or MARKER not in value:
        return value
    size, data = value.get("plain_bytes"), value.get("data")
    if (
        set(value) != {MARKER, "plain_bytes", "data"}
        or value[MARKER] != VERSION
        or not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 < size <= MAX_STATE_BYTES
        or not isinstance(data, str)
        or len(data) > (MAX_STATE_BYTES + 1024) * 4 // 3
    ):
        raise ValueError("Unsupported or invalid paper state encoding")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(base64.b64decode(data, validate=True), size + 1)
        if len(raw) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Paper state encoding length or stream mismatch")
        result = json.loads(raw)
    except (ValueError, UnicodeError, binascii.Error, zlib.error) as error:
        raise ValueError("Invalid compressed paper account") from error
    if not isinstance(result, dict) or MARKER in result:
        raise ValueError("Compressed paper state must be a logical account object")
    return result
