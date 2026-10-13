"""Explicit challenge-only settlement revisions; legacy generation stays immutable."""

from typing import Literal

from midas.core.models import Model, Source
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario


class GeneratorRevision(Model):
    version: Literal["hashed-settlement-1"] = "hashed-settlement-1"

    def apply(self, scenario: Scenario) -> Scenario:
        if scenario.provenance != "GENERATED" or scenario.market.source != Source.SYNTHETIC:
            raise ValueError("Generator revisions require synthetic generated scenarios")
        assets = tuple(instrument.asset_id for instrument in scenario.market.instruments)
        if len(assets) != 2 or len(set(assets)) != 2 or set(assets) != set(scenario.books):
            raise ValueError("Settlement revision requires binary scenarios")
        winner = int(digest([self.version, "settlement", scenario.seed])[:16], 16) % 2
        events = []
        for event in scenario.events:
            if event.kind == "settle":
                if set(event.payload.get("payout", {})) != set(assets):
                    raise ValueError("Unexpected settlement asset coverage")
                event = event.model_copy(
                    update={
                        "payload": {
                            **event.payload,
                            "payout": {
                                asset: str(int(i == winner)) for i, asset in enumerate(assets)
                            },
                        }
                    }
                )
            events.append(event)
        return scenario.model_copy(
            update={
                "events": tuple(events),
                "warnings": (
                    *scenario.warnings,
                    "Challenge-only hashed settlement removes direct seed-parity outcome rule; uncalibrated synthetic outcomes",
                ),
            }
        )
