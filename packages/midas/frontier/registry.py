"""Capability registry for source adapters; registrations never activate networking."""

from __future__ import annotations

from collections.abc import Iterable

from midas.frontier.adapters import (
    CoinbaseSpotAdapter,
    GeminiSpotAdapter,
    KalshiAdapter,
    KrakenSpotAdapter,
    PolymarketAdapter,
)
from midas.frontier.adapters.base import ExchangeAdapter
from midas.frontier.models import AdapterCapabilities, SourceHealth, Venue


class AdapterRegistry:
    def __init__(self, adapters: Iterable[ExchangeAdapter] = ()) -> None:
        self._adapters: dict[Venue, ExchangeAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ExchangeAdapter) -> None:
        if adapter.venue != adapter.capabilities.venue:
            raise ValueError("Adapter venue and capability manifest disagree")
        if adapter.venue in self._adapters:
            raise ValueError(f"An adapter is already registered for {adapter.venue.value}")
        self._adapters[adapter.venue] = adapter

    def get(self, venue: Venue) -> ExchangeAdapter:
        return self._adapters[venue]

    def capability_manifests(self) -> tuple[AdapterCapabilities, ...]:
        return tuple(self._adapters[venue].capabilities for venue in sorted(self._adapters))

    async def health(self) -> tuple[SourceHealth, ...]:
        return tuple([await self._adapters[venue].health() for venue in sorted(self._adapters)])

    async def aclose(self) -> None:
        for adapter in self._adapters.values():
            close = getattr(adapter, "aclose", None)
            if close is not None:
                await close()


def default_registry() -> AdapterRegistry:
    """Return all implemented adapters disabled by default; no startup probe occurs."""
    return AdapterRegistry(
        (
            PolymarketAdapter(),
            KalshiAdapter(),
            KrakenSpotAdapter(),
            CoinbaseSpotAdapter(),
            GeminiSpotAdapter(),
        )
    )
