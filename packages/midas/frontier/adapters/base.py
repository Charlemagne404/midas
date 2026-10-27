"""Adapter contract and capability construction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from midas.frontier.models import (
    AdapterCapabilities,
    AdapterConfig,
    BookSnapshot,
    Capability,
    CapabilityDeclaration,
    FrontierMarket,
    MarketBatch,
    RawObservation,
    SourceHealth,
    SourceState,
    TradeObservation,
    Venue,
)

if TYPE_CHECKING:
    from midas.frontier.adapters.transport import PublicReadTransport


@dataclass(frozen=True, slots=True)
class FailedResponseEvidence:
    """Complete, bounded HTTP response bytes retained with a transport failure."""

    url: str
    status_code: int
    raw_body: bytes
    request_started_at_utc: datetime
    response_received_at_utc: datetime


class AdapterError(RuntimeError):
    """A classified public-source or normalization failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        response_evidence: FailedResponseEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.response_evidence = response_evidence


class UnsupportedCapability(AdapterError):
    def __init__(self, capability: Capability, reason: str) -> None:
        super().__init__("UNSUPPORTED_CAPABILITY", f"{capability.value}: {reason}")
        self.capability = capability


@runtime_checkable
class ExchangeAdapter(Protocol):
    venue: Venue
    capabilities: AdapterCapabilities
    config: AdapterConfig
    transport: PublicReadTransport

    async def health(self) -> SourceHealth: ...

    async def discover_markets(self, limit: int = 20) -> tuple[FrontierMarket, ...]: ...

    async def discover_event_markets(self, native_event_id: str) -> tuple[FrontierMarket, ...]: ...

    async def discover_multivariate_events(
        self,
        *,
        series_ticker: str | None = None,
        collection_ticker: str | None = None,
        event_ticker: str | None = None,
    ) -> MarketBatch: ...

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot: ...

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]: ...

    def take_captures(self) -> tuple[RawObservation, ...]: ...

    def report_failure(self, code: str, message: str) -> None: ...


class BaseReadOnlyAdapter:
    """Common disabled-by-default lifecycle for public GET-only adapters."""

    venue: Venue
    capabilities: AdapterCapabilities
    allowed_hosts: set[str]

    def __init__(
        self,
        config: AdapterConfig | None = None,
        *,
        transport: PublicReadTransport | None = None,
    ) -> None:
        from midas.frontier.adapters.transport import PublicReadTransport

        self.config = config or AdapterConfig()
        self.transport = transport or PublicReadTransport(self.allowed_hosts, self.config)
        self._captures: list[RawObservation] = []
        self._capture_bytes = 0
        self._last_success: datetime | None = None
        self._last_error_code: str | None = None
        self._last_error: str | None = None

    async def health(self) -> SourceHealth:
        supported = tuple(
            item.capability for item in self.capabilities.declarations if item.supported
        )
        unsupported = tuple(
            item.capability for item in self.capabilities.declarations if not item.supported
        )
        state = (
            SourceState.DEGRADED
            if self._last_error_code is not None
            else SourceState.HEALTHY
            if self._last_success is not None
            else SourceState.NOT_PROBED
        )
        return SourceHealth(
            venue=self.venue,
            state=state,
            checked_at_utc=now_utc(),
            last_success_at_utc=self._last_success,
            last_error_code=self._last_error_code,
            last_error=self._last_error,
            requests_in_window=self.transport.requests_in_window(),
            supported_capabilities=supported,
            unsupported_capabilities=unsupported,
            notes=(
                "Health read is local state and makes no network request.",
                "Request count covers the trailing 60 seconds.",
            ),
        )

    def _capture_response(self, response: Any, observation_kind: str) -> RawObservation:
        from hashlib import sha256

        raw = response.raw_body.encode("utf-8")
        if self._capture_bytes + len(raw) > 2 * 1024 * 1024 or len(self._captures) >= 32:
            raise AdapterError(
                "CAPTURE_BUDGET_EXCEEDED", "In-memory response capture budget is exhausted"
            )
        capture = RawObservation(
            venue=self.venue,
            observation_kind=observation_kind,
            request_url=response.url,
            http_status=response.status_code,
            request_started_at_utc=response.request_started_at_utc,
            received_at_utc=response.response_received_at_utc,
            raw_body=response.raw_body,
            raw_sha256=sha256(raw).hexdigest(),
            adapter_version=self.capabilities.adapter_version,
        )
        self._captures.append(capture)
        self._capture_bytes += len(raw)
        self._last_success = response.response_received_at_utc
        self._last_error_code = None
        self._last_error = None
        return capture

    async def discover_event_markets(self, native_event_id: str) -> tuple[FrontierMarket, ...]:
        """Fail closed unless a venue implements bounded event-group discovery."""
        self._require(Capability.EVENT_MARKET_GROUPS)
        raise UnsupportedCapability(
            Capability.EVENT_MARKET_GROUPS,
            f"{self.venue.value} does not implement event-group discovery",
        )

    async def discover_multivariate_events(
        self,
        *,
        series_ticker: str | None = None,
        collection_ticker: str | None = None,
        event_ticker: str | None = None,
    ) -> MarketBatch:
        """Fail closed unless a venue implements bounded multivariate-event discovery."""
        del series_ticker, collection_ticker, event_ticker
        self._require(Capability.MULTIVARIATE_EVENT_DISCOVERY)
        raise UnsupportedCapability(
            Capability.MULTIVARIATE_EVENT_DISCOVERY,
            f"{self.venue.value} does not implement multivariate-event discovery",
        )

    def take_captures(self) -> tuple[RawObservation, ...]:
        captures = tuple(self._captures)
        self._captures.clear()
        self._capture_bytes = 0
        return captures

    def report_failure(self, code: str, message: str) -> None:
        self._last_error_code = code[:80]
        self._last_error = message[:240]

    async def aclose(self) -> None:
        await self.transport.close()

    def _require(self, capability: Capability) -> None:
        if not self.capabilities.supports(capability):
            declaration = next(
                item for item in self.capabilities.declarations if item.capability == capability
            )
            raise UnsupportedCapability(capability, declaration.reason)


def build_capabilities(
    venue: Venue,
    adapter_version: str,
    supported: Mapping[Capability, tuple[str, str | None]],
    unsupported: Mapping[Capability, tuple[str, str | None]] | None = None,
) -> AdapterCapabilities:
    """Create a complete declaration; omitted entries fail closed as unsupported."""
    unsupported = unsupported or {}
    declarations = []
    for capability in Capability:
        if capability in supported:
            reason, doc = supported[capability]
            declarations.append(
                CapabilityDeclaration(
                    capability=capability,
                    supported=True,
                    state="implemented",
                    reason=reason,
                    documentation_url=doc,
                )
            )
        else:
            reason, doc = unsupported.get(capability, ("Not implemented by this adapter", None))
            declarations.append(
                CapabilityDeclaration(
                    capability=capability,
                    supported=False,
                    state="unsupported",
                    reason=reason,
                    documentation_url=doc,
                )
            )
    return AdapterCapabilities(
        venue=venue,
        adapter_version=adapter_version,
        declarations=tuple(declarations),
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
