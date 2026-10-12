"""Declared synthetic economic perturbations applied before planning and execution."""

from decimal import Decimal
from typing import Any

from pydantic import Field

from midas.core.models import Book, Market, Model, Source
from midas.laboratory.spec import Costs, Scenario


class EconomicRegime(Model):
    version: str = "economic-regime-1"
    depth_multiplier: Decimal = Field(default=Decimal(1), ge=0, le=2, allow_inf_nan=False)
    taker_fee_rate: Decimal | None = Field(default=None, ge=0, le=0.25, allow_inf_nan=False)
    additional_submission_latency_ms: int = Field(default=0, ge=0, le=10000)
    costs: Costs | None = None

    def apply(self, scenario: Scenario) -> Scenario:
        if scenario.provenance != "GENERATED":
            raise ValueError(
                "Economic perturbations require generated scenarios; recorded observations stay immutable"
            )
        if (
            self.depth_multiplier == 1
            and self.taker_fee_rate is None
            and not self.additional_submission_latency_ms
            and self.costs is None
        ):
            return scenario

        def book(value: Any) -> Book:
            original = Book.model_validate(value)
            if original.source != Source.SYNTHETIC:
                raise ValueError("Cannot perturb observed public depth")
            return original.model_copy(
                update={
                    side: tuple(
                        level.model_copy(update={"size": level.size * self.depth_multiplier})
                        for level in getattr(original, side)
                    )
                    if self.depth_multiplier
                    else ()
                    for side in ("asks", "bids")
                }
            )

        def market(value: Any) -> Market:
            original = Market.model_validate(value)
            if self.taker_fee_rate is None:
                return original
            if original.source != Source.SYNTHETIC:
                raise ValueError("Cannot rewrite observed market fees")
            return original.model_copy(
                update={
                    "fee": original.fee.model_copy(
                        update={
                            "rate": self.taker_fee_rate,
                            "verified": True,
                            "evidence": "Declared synthetic sensitivity parameter, not observed fees",
                        }
                    )
                }
            )

        events = []
        for event in scenario.events:
            payload = dict(event.payload)
            if "books" in payload:
                payload["books"] = {
                    asset: book(value).model_dump(mode="json")
                    for asset, value in payload["books"].items()
                }
            if "market" in payload:
                payload["market"] = market(payload["market"]).model_dump(mode="json")
            events.append(event.model_copy(update={"payload": payload}))
        execution = scenario.account.execution.model_copy(
            update={
                "latency_ms": scenario.account.execution.latency_ms
                + self.additional_submission_latency_ms
            }
        )
        # Validate the combined latency against the existing execution contract.
        execution = type(execution).model_validate(execution.model_dump(mode="json"))
        return scenario.model_copy(
            update={
                "books": {asset: book(value) for asset, value in scenario.books.items()},
                "market": market(scenario.market),
                "events": tuple(events),
                "account": scenario.account.model_copy(update={"execution": execution}),
                "costs": self.costs or scenario.costs,
                "warnings": (
                    *scenario.warnings,
                    "Synthetic economic regime; no observed fees or execution calibration",
                ),
            }
        )
