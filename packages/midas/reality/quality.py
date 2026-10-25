"""Independent public-book comparisons; no exchange sequence guarantee implied."""

from __future__ import annotations

import hashlib
import time
from decimal import Decimal
from typing import Any

from .storage import canonical


def exact_decimal(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def levels(raw: Any) -> dict[str, str]:
    """Independent REST depth validation, deliberately separate from Engine.number."""
    if not isinstance(raw, list) or len(raw) > 10000:
        raise ValueError("Invalid comparison book levels")
    result = {}
    for level in raw:
        if not isinstance(level, dict):
            raise ValueError("Invalid comparison level")
        if any(not isinstance(level.get(k), str) or len(level[k]) > 80 for k in ("price", "size")):
            raise ValueError("Comparison decimal values must be bounded strings")
        price, size = Decimal(level["price"]), Decimal(level["size"])
        if not price.is_finite() or not size.is_finite() or not 0 <= price <= 1 or size < 0:
            raise ValueError("Invalid comparison price or size")
        if any(abs(int(x.as_tuple().exponent)) > 40 for x in (price, size)):
            raise ValueError("Comparison decimal exponent out of range")
        key = exact_decimal(price)
        if key in result:
            raise ValueError("Duplicate comparison level")
        if size:
            result[key] = exact_decimal(size)
    return result


def depth_state(book: dict[str, Any] | None) -> dict[str, Any] | None:
    if book is None:
        return None
    return dict(
        last=list(book["last"]),
        snapshot=list(book["snapshot"]),
        received_ns=book["received_ns"],
        issue=book["issue"],
        bids={exact_decimal(p): exact_decimal(q) for p, q in book["bids"].items()},
        asks={exact_decimal(p): exact_decimal(q) for p, q in book["asks"].items()},
    )


def compare(
    raw: dict[str, Any],
    *,
    asset: str,
    condition: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    request_ns: int,
    response_ns: int,
    stale_ns: int,
) -> dict[str, Any]:
    if raw.get("asset_id") != asset or raw.get("market") != condition:
        raise ValueError("Independent book asset/condition mismatch")
    external = {side: levels(raw.get(side)) for side in ("bids", "asks")}
    stamp = int(raw["timestamp"])
    if stamp < 0 or response_ns < request_ns:
        raise ValueError("Invalid comparison timestamp")
    result = dict(
        asset_id=asset,
        condition=condition,
        request_ns=request_ns,
        response_ns=response_ns,
        round_trip_ns=response_ns - request_ns,
        source_timestamp_ms=stamp,
        source_native_hash=raw.get("hash"),
        independent_depth_sha256=hashlib.sha256(canonical(external)).hexdigest(),
        before_lineage=before["last"] if before else None,
        after_lineage=after["last"] if after else None,
        sequence_verified=False,
        limitation=(
            "HTTP round trip is not one-way latency; a cross-interface depth mismatch at stable local lineage "
            "does not identify which view is incomplete without an upstream sequence or atomic cross-interface snapshot."
        ),
    )
    if not before or not after or before["issue"] or after["issue"]:
        result["assessment"] = "ineligible_local_state"
    elif response_ns - after["received_ns"] > stale_ns:
        result["assessment"] = "stale_local_state"
    elif before["last"] != after["last"] or before["snapshot"] != after["snapshot"]:
        result["assessment"] = "concurrent_updates_ambiguous"
    else:
        local = {side: before[side] for side in ("bids", "asks")}
        differences = {
            side: sum(
                before[side].get(price) != external[side].get(price)
                for price in before[side].keys() | external[side].keys()
            )
            for side in ("bids", "asks")
        }
        result["local_depth_sha256"] = hashlib.sha256(canonical(local)).hexdigest()
        result["local_level_counts"] = {side: len(before[side]) for side in ("bids", "asks")}
        result["independent_level_counts"] = {
            side: len(external[side]) for side in ("bids", "asks")
        }
        result["depth_difference_counts"] = differences
        result["assessment"] = (
            "stable_local_lineage_divergence"
            if any(differences.values())
            else "stable_local_lineage_match_unsequenced"
        )
    return result


def clock_health() -> dict[str, Any]:
    """Linux kernel synchronization flags; no claim of exact absolute clock error."""
    import ctypes
    import sys

    if sys.platform != "linux":
        return dict(status="unknown", reason="kernel synchronization probe unavailable")

    # ntp_gettime uses a Linux ntptimeval of four longs followed by four reserved longs.
    class NtpTime(ctypes.Structure):
        _fields_ = [
            ("seconds", ctypes.c_long),
            ("microseconds", ctypes.c_long),
            ("maxerror", ctypes.c_long),
            ("esterror", ctypes.c_long),
            ("tai", ctypes.c_long),
            ("reserved", ctypes.c_long * 4),
        ]

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.ntp_gettime
        fn.argtypes, fn.restype = [ctypes.POINTER(NtpTime)], ctypes.c_int
        state = NtpTime()
        code = fn(ctypes.byref(state))
        return dict(
            status="kernel_synchronized" if code == 0 else "kernel_unsynchronized_or_leap",
            kernel_state=code,
            maximum_error_us=state.maxerror,
            estimated_error_us=state.esterror,
            checked_ns=time.time_ns(),
            limitation="Kernel-reported clock health; not independently measured venue clock skew.",
        )
    except (AttributeError, OSError):
        return dict(status="unknown", reason="kernel synchronization probe failed")
