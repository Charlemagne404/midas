"""Adapter contract and capability construction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from midas.frontier.models import (
    AdapterCapabilities,
    AdapterConfig,
    BookSnapshot,
    Capability,
    CapabilityDeclaration,
    FrontierMarket,
    MarketBatch,
    PriceHistorySeries,
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
    request_elapsed_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class RejectedResponseEvidence:
    """Bounded metadata for a response rejected before its complete body was retained."""

    url: str
    status_code: int
    request_started_at_utc: datetime
    rejected_at_utc: datetime
    request_elapsed_monotonic_ns: int
    max_response_bytes: int
    declared_content_length_bytes: int | None
    bytes_yielded_at_rejection: int
    rejection_stage: Literal["content_length", "response_stream"]


class AdapterError(RuntimeError):
    """A classified public-source or normalization failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        response_evidence: FailedResponseEvidence | None = None,
        response_diagnostic: RejectedResponseEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.response_evidence = response_evidence
        self.response_diagnostic = response_diagnostic


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


@runtime_checkable
class SingleMarketMetadataAdapter(Protocol):
    """Optional extension for capability-specific exact native-ID detail lookups."""

    async def fetch_market_metadata(self, native_market_id: str) -> FrontierMarket: ...

    def market_metadata_request_url(self, native_market_id: str) -> str: ...


@runtime_checkable
class PriceHistoryAdapter(Protocol):
    """Optional extension for source-specific historical price samples."""

    async def fetch_price_history(
        self,
        native_instrument_id: str,
        *,
        interval: Literal["1d", "1w"],
        fidelity_minutes: int,
        start_ts: int,
        end_ts: int,
    ) -> PriceHistorySeries: ...


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
        if not self.config.has_valid_structure:
            raise ValueError("Adapter configuration fails structural validation")
        if transport is not None:
            if type(transport.config) is not type(self.config) or transport.config != self.config:
                raise ValueError(
                    "Adapter transport configuration differs from adapter configuration"
                )
            expected_hosts = frozenset(host.lower() for host in self.allowed_hosts)
            if not transport.allowed_hosts <= expected_hosts:
                raise ValueError("Adapter transport host allowlist exceeds adapter source")
        self.transport = (
            transport
            if transport is not None
            else PublicReadTransport(self.allowed_hosts, self.config)
        )
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
                *(
                    (self.config.probe_policy_block_reason,)
                    if self.config.probe_policy_block_reason is not None
                    else ()
                ),
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
            request_elapsed_monotonic_ns=response.request_elapsed_monotonic_ns,
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
