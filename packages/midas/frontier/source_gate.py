"""Fail-fast, process-local admission for bounded public-source operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from midas.frontier.models import Venue

MAX_CONCURRENT_SOURCE_OPERATIONS = 2
SOURCE_OPERATION_ACQUIRE_TIMEOUT_SECONDS = 0.05


class SourceOperationBusy(RuntimeError):
    """A source operation could not acquire bounded local capacity promptly."""

    def __init__(self, venue: Venue, scope: str) -> None:
        if scope not in {"venue", "capacity"}:
            raise ValueError("Source-operation busy scope is invalid")
        self.venue = venue
        self.scope = scope
        detail = (
            "another operation for this venue is active"
            if scope == "venue"
            else "the shared source-operation capacity is full"
        )
        super().__init__(f"Public source operation is busy: {detail}")


class BoundedSourceOperationGate:
    """One in-flight operation per venue and a small process-wide concurrency cap.

    Waiting is deliberately brief and fail-fast. This provides backpressure
    without accumulating a queue of requests in the API process. Each router
    instance owns its own gate; it is not a cross-process coordinator.
    """

    def __init__(
        self,
        *,
        max_concurrent: int = MAX_CONCURRENT_SOURCE_OPERATIONS,
        acquire_timeout_seconds: float = SOURCE_OPERATION_ACQUIRE_TIMEOUT_SECONDS,
    ) -> None:
        if type(max_concurrent) is not int or not 1 <= max_concurrent <= 8:
            raise ValueError("max_concurrent must be an integer from one to eight")
        if (
            isinstance(acquire_timeout_seconds, bool)
            or not isinstance(acquire_timeout_seconds, (int, float))
            or not 0 < acquire_timeout_seconds <= 1
        ):
            raise ValueError("acquire_timeout_seconds must be within (0, 1]")
        self.max_concurrent = max_concurrent
        self.acquire_timeout_seconds = float(acquire_timeout_seconds)
        self._capacity = asyncio.BoundedSemaphore(max_concurrent)
        self._venue_locks = {venue: asyncio.Lock() for venue in Venue}
        self._active_venues: set[Venue] = set()
        self._admitted_operations_total = 0
        self._busy_rejections_by_scope = {"venue": 0, "capacity": 0}

    def runtime_snapshot(self) -> dict[str, object]:
        """Return bounded counters scoped to this router instance's lifetime."""
        rejected_by_scope = dict(self._busy_rejections_by_scope)
        return {
            "active_operations": len(self._active_venues),
            "active_venues": sorted(venue.value for venue in self._active_venues),
            "admitted_operations_total": self._admitted_operations_total,
            "busy_rejections_total": sum(rejected_by_scope.values()),
            "busy_rejections_by_scope": rejected_by_scope,
        }

    @asynccontextmanager
    async def operation(self, venue: Venue) -> AsyncIterator[None]:
        if not isinstance(venue, Venue):
            raise ValueError("Source-operation venue must be a registered Venue")
        venue_lock = self._venue_locks[venue]
        owns_venue = False
        owns_capacity = False
        try:
            try:
                await asyncio.wait_for(venue_lock.acquire(), timeout=self.acquire_timeout_seconds)
            except TimeoutError as error:
                self._busy_rejections_by_scope["venue"] += 1
                raise SourceOperationBusy(venue, "venue") from error
            owns_venue = True
            try:
                await asyncio.wait_for(
                    self._capacity.acquire(), timeout=self.acquire_timeout_seconds
                )
            except TimeoutError as error:
                self._busy_rejections_by_scope["capacity"] += 1
                raise SourceOperationBusy(venue, "capacity") from error
            owns_capacity = True
            self._active_venues.add(venue)
            self._admitted_operations_total += 1
            yield
        finally:
            if owns_capacity:
                self._active_venues.remove(venue)
                self._capacity.release()
            if owns_venue:
                venue_lock.release()
