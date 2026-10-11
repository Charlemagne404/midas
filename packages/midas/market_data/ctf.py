"""Read-only, fixed-contract Polygon attestation. No transaction/signing RPC exists."""

import asyncio
from typing import Any

import httpx
from eth_hash.auto import keccak

from midas.core.models import Market
from midas.economics.attestation import COLLATERAL, CTF, MarketEconomicAttestation, attest
from midas.market_data.polymarket import now_ms


class CTFVerifier:
    def __init__(
        self,
        url: str = "https://polygon-bor-rpc.publicnode.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.client = httpx.AsyncClient(timeout=15, transport=transport)
        self.calls: list[dict[str, Any]] = []

    async def _read(self, method: str, params: list[Any]) -> Any:
        if method not in {"eth_chainId", "eth_getBlockByNumber", "eth_call"}:
            raise ValueError("Only structural chain reads permitted")
        await asyncio.sleep(0.2)
        response = await self.client.post(
            self.url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        )
        response.raise_for_status()
        raw = response.json()
        if "error" in raw or "result" not in raw:
            raise ValueError("Invalid RPC read response")
        self.calls.append(
            {
                "method": method,
                "params": params,
                "result": {k: raw["result"][k] for k in ("number", "hash", "timestamp")}
                if method == "eth_getBlockByNumber"
                else raw["result"],
            }
        )
        return raw["result"]

    async def verify(self, market: Market) -> MarketEconomicAttestation:
        self.calls = []
        evidence: dict[str, Any] = {"rpc_url": self.url}
        if market.protocol != "v1" or market.negative_risk or market.augmented_negative_risk:
            return attest(market, evidence, now_ms())
        try:
            condition = bytes.fromhex(market.condition_id.removeprefix("0x"))
            if len(condition) != 32:
                raise ValueError("CTF condition must be bytes32")
            chain = int(await self._read("eth_chainId", []), 16)
            block = await self._read("eth_getBlockByNumber", ["finalized", False])
            tag = block["number"]

            async def call(signature: str, arguments: bytes) -> bytes:
                data = "0x" + (keccak(signature.encode())[:4] + arguments).hex()
                result = await self._read("eth_call", [{"to": CTF, "data": data}, tag])
                value = bytes.fromhex(result.removeprefix("0x"))
                if len(value) != 32:
                    raise ValueError("Invalid ABI result length")
                return value

            slots = int.from_bytes(await call("getOutcomeSlotCount(bytes32)", condition))
            denominator = int.from_bytes(await call("payoutDenominator(bytes32)", condition))
            ids = []
            for index in (1, 2):
                col = await call(
                    "getCollectionId(bytes32,bytes32,uint256)",
                    bytes(32) + condition + index.to_bytes(32),
                )
                pos = await call(
                    "getPositionId(address,bytes32)",
                    bytes(12) + bytes.fromhex(COLLATERAL[2:]) + col,
                )
                ids.append(str(int.from_bytes(pos)))
            evidence.update(
                chain_id=chain,
                contract=CTF,
                collateral=COLLATERAL,
                condition_id=market.condition_id,
                outcome_slot_count=slots,
                payout_denominator=denominator,
                position_ids=ids,
                index_sets=[1, 2],
                parent_collection="0x" + "00" * 32,
                block_hash=block["hash"],
                block_number=tag,
                calls=self.calls,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            evidence.update(error=f"{type(error).__name__}: {error}", calls=self.calls)
        return attest(market, evidence, now_ms())

    async def resolution(self, market: Market) -> dict[str, Any] | None:
        if market.protocol != "v1" or market.attestation is None:
            return None
        self.calls = []
        chain = int(await self._read("eth_chainId", []), 16)
        block = await self._read("eth_getBlockByNumber", ["finalized", False])
        condition = bytes.fromhex(market.condition_id.removeprefix("0x"))
        if len(condition) != 32 or chain != 137:
            raise ValueError("Invalid settlement identity")

        async def read(signature: str, args: bytes) -> int:
            result = await self._read(
                "eth_call",
                [
                    {"to": CTF, "data": "0x" + (keccak(signature.encode())[:4] + args).hex()},
                    block["number"],
                ],
            )
            value = bytes.fromhex(result.removeprefix("0x"))
            if len(value) != 32:
                raise ValueError("Malformed terminal payout response")
            return int.from_bytes(value)

        denominator = await read("payoutDenominator(bytes32)", condition)
        if denominator == 0:
            return None
        numerators = [
            await read("payoutNumerators(bytes32,uint256)", condition + i.to_bytes(32))
            for i in (0, 1)
        ]
        if sum(numerators) != denominator:
            raise ValueError("Contradictory resolved payout vector")
        return {
            "chain_id": chain,
            "contract": CTF,
            "condition_id": market.condition_id,
            "block_hash": block["hash"],
            "denominator": denominator,
            "numerators": {
                i.asset_id: n for i, n in zip(market.instruments, numerators, strict=True)
            },
            "calls": self.calls,
            "rpc_url": self.url,
            "observed_ts_ms": now_ms(),
        }

    async def close(self) -> None:
        await self.client.aclose()
