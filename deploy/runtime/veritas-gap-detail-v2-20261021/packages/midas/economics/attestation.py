"""Versioned structural evidence. Natural-language rules are never mathematical proof."""

import hashlib
import json
from typing import Any

from midas.core.models import Market, Model

VERSION = "ctf-complement-2"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
COLLATERAL = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
SOURCES = (
    "https://docs.polymarket.com/resources/onchain-position-data",
    "https://docs.polymarket.com/concepts/positions-tokens",
    "https://docs.polymarket.com/concepts/resolution",
    "https://docs.polymarket.com/resources/contracts",
)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def fingerprint(market: Market) -> str:
    data = market.model_dump(mode="json")
    for name in ("attestation", "payout_evidence", "payout_verified", "complementary_verified"):
        data.pop(name, None)
    for name in ("verified_ts_ms", "expires_ts_ms"):
        data["fee"].pop(name, None)
    return digest(data)


class MarketEconomicAttestation(Model):
    market_id: str
    condition_id: str
    protocol: str
    instruments: tuple[str, ...]
    status: str
    relationship: str = "Not established"
    terminal_outcomes: tuple[str, ...] = ()
    collateral: str = COLLATERAL
    position_system: str = CTF
    resolution_mechanism: str = "CTF oracle reportPayouts; exact oracle identity unresolved"
    rule_version: str
    metadata_hash: str
    method: str = VERSION
    verified_ts_ms: int
    expires_ts_ms: int
    evidence: dict[str, Any]
    sources: tuple[str, ...] = SOURCES
    reasons: tuple[str, ...] = ()
    invalidation: tuple[str, ...] = (
        "Metadata/rules/instrument/fee/state change",
        "Evidence expiry",
        "RPC chain or contract contradiction",
    )
    unresolved_assumptions: tuple[str, ...] = (
        "RPC provider reports authentic finalized chain state",
        "CTF implementation and collateral continue operating correctly",
        "USDC.e backing retains value; pUSD conversion is modeled at parity, not independently attested",
        "Natural-language resolution rules not mathematically proven or human-reviewed",
        "Settlement timing, gas and financing costs are not established",
    )

    def valid_for(self, market: Market, now_ms: int) -> bool:
        return (
            self.method == VERSION
            and self.status == "VERIFIED_STRUCTURE"
            and self.metadata_hash == fingerprint(market)
            and self.verified_ts_ms <= now_ms <= self.expires_ts_ms
            and self.market_id == market.id
            and self.condition_id == market.condition_id
            and self.instruments == tuple(i.asset_id for i in market.instruments)
        )


def attest(market: Market, evidence: dict[str, Any], ts: int) -> MarketEconomicAttestation:
    reasons = []
    if market.payout_per_set != 1:
        reasons.append("Supported CTF complete-set backing is exactly one collateral unit")
    if market.protocol != "v1":
        reasons.append(
            "Live Protocol V2 structural verification unsupported; fixture routing is not live evidence"
        )
    if market.negative_risk or market.augmented_negative_risk:
        reasons.append("Negative-risk and augmented structures unsupported")
    if not market.active or market.closed or not market.accepting_orders:
        reasons.append("Market inactive, closed or paused")
    if len(market.instruments) != 2 or len({i.asset_id for i in market.instruments}) != 2:
        reasons.append("Requires two distinct outcome instruments")
    if not market.description:
        reasons.append("Missing descriptive resolution rules")
    expected = tuple(i.asset_id for i in market.instruments)
    if (
        evidence.get("chain_id") != 137
        or evidence.get("contract") != CTF
        or evidence.get("collateral") != COLLATERAL
        or evidence.get("condition_id") != market.condition_id
        or evidence.get("outcome_slot_count") != 2
        or evidence.get("index_sets") != [1, 2]
        or tuple(evidence.get("position_ids", [])) != expected
        or evidence.get("parent_collection") != "0x" + "00" * 32
        or evidence.get("payout_denominator") != 0
        or not evidence.get("block_hash")
        or not evidence.get("calls")
    ):
        reasons.append("Missing or contradictory deployed CTF structural evidence")
    return MarketEconomicAttestation(
        market_id=market.id,
        condition_id=market.condition_id,
        protocol=market.protocol,
        instruments=expected,
        status="REJECTED" if reasons else "VERIFIED_STRUCTURE",
        relationship="For any nonnegative CTF payout vector (a,b), denominator=a+b>0; equal singleton quantities pay q collateral units"
        if not reasons
        else "Not established",
        terminal_outcomes=("FIRST: (1,0)", "SECOND: (0,1)", "SPLIT: (t,1-t), 0<=t<=1")
        if not reasons
        else (),
        rule_version=digest(
            {
                "description": market.description,
                "source": market.resolution_source,
                "metadata": market.resolution_metadata,
            }
        ),
        metadata_hash=fingerprint(market),
        verified_ts_ms=ts,
        expires_ts_ms=ts + 300_000,
        evidence=evidence,
        reasons=tuple(reasons),
    )
