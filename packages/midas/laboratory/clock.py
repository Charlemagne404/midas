"""Checkpointable event heap. Ordering is time, priority, insertion ordinal."""

import copy
import heapq
from dataclasses import asdict, dataclass, field
from typing import Any

from midas.economics.attestation import digest


@dataclass(order=True)
class Event:
    time: int
    priority: int
    ordinal: int
    id: str = field(compare=False)
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False)


class Clock:
    def __init__(self) -> None:
        self.now = 0
        self.ordinal = 0
        self.heap: list[Event] = []
        self.identities: dict[str, str] = {}
        self.cancelled: set[str] = set()

    def schedule(
        self, time: int, id: str, kind: str, payload: dict[str, Any], priority: int = 10
    ) -> None:
        if time < self.now:
            raise ValueError("Cannot schedule into the virtual past")
        fingerprint = digest([time, kind, payload, priority])
        if id in self.identities:
            if self.identities[id] != fingerprint:
                raise ValueError("Conflicting scheduled event identity")
            return
        self.identities[id] = fingerprint
        self.ordinal += 1
        heapq.heappush(
            self.heap, Event(time, priority, self.ordinal, id, kind, copy.deepcopy(payload))
        )

    def cancel(self, id: str) -> None:
        self.cancelled.add(id)

    def replace(self, old: str, time: int, id: str, kind: str, payload: dict[str, Any]) -> None:
        self.schedule(time, id, kind, payload)
        self.cancel(old)

    def peek(self) -> Event | None:
        while self.heap and self.heap[0].id in self.cancelled:
            heapq.heappop(self.heap)
        return self.heap[0] if self.heap else None

    def pop(self) -> Event:
        if self.peek() is None:
            raise IndexError("Empty event queue")
        event = heapq.heappop(self.heap)
        self.now = event.time
        return event

    def checkpoint(self) -> dict[str, Any]:
        return {
            "now": self.now,
            "ordinal": self.ordinal,
            "events": [asdict(e) for e in sorted(self.heap)],
            "identities": self.identities,
            "cancelled": sorted(self.cancelled),
        }

    @classmethod
    def restore(cls, data: dict[str, Any]) -> "Clock":
        clock = cls()
        clock.now, clock.ordinal = data["now"], data["ordinal"]
        clock.heap = [Event(**e) for e in data["events"]]
        heapq.heapify(clock.heap)
        clock.identities = dict(data["identities"])
        clock.cancelled = set(data["cancelled"])
        if any(e.time < clock.now for e in clock.heap if e.id not in clock.cancelled):
            raise ValueError("Checkpoint contains past events")
        return clock
