import json
from decimal import Decimal
from pathlib import Path

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Market
from midas.market_data.recording import replay

root = Path(__file__).resolve().parents[1] / "data" / "samples"
markets = {
    m.id: m
    for raw in json.loads((root / "markets.json").read_text())
    if (m := Market.model_validate(raw))
}
results = replay(root / "synthetic-events.jsonl", markets, BinaryStrategy(), Decimal(1000))
print(
    json.dumps(
        {
            "context": "HISTORICAL_REPLAY",
            "original_source": "SYNTHETIC",
            "execution": "not estimated from snapshots by replay",
            "evaluations": [
                {"market": e.market_id, "status": e.status, "net_profit": str(e.net_profit)}
                for e in results
            ],
        },
        indent=2,
    )
)
