"""Read-only financing evidence around the unchanged Laboratory transitions."""

from typing import Any

from midas.laboratory.runtime import Environment
from midas.simulation.exchange import Exchange


class CostEnvironment(Environment):
    def reset(self) -> dict[str, Any]:
        self.financing_trace: list[dict[str, Any]] = []
        return super().reset()

    def _accrue(self, ts: int, portfolio: dict[str, Any] | None = None) -> None:
        if self.state["positions"] and ts > self.last_ts:
            identity = next(iter(self.state["positions"]))
            snapshot = self.state["positions"][identity]["exchange"]
            exchange = Exchange.restore(snapshot)
            pending = [a["id"] for a in self.state["pending"] if a["position"] == identity]
            self.financing_trace.append(
                {
                    "position_id": identity,
                    "start_ms": self.last_ts,
                    "end_ms": ts,
                    "ledger_count": len(snapshot["ledger"]),
                    "pending_action_ids": pending,
                    "available_usd": str(exchange.portfolio.available),
                    "reserved_usd": str(exchange.portfolio.reserved),
                    "locked_usd": str(exchange.portfolio.locked),
                }
            )
        super()._accrue(ts, portfolio)
