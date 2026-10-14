# Reality engine — Mission 1 (in progress)

Isolated branch `project/reality`, baseline `8acab22`. Runtime data stays in this
worktree's `data/recordings`; the production API, financial simulation and
protected research stores are not modified.

Implementation order: validate public contracts; start bounded durable capture;
add reconstruction/replay and failure tests; deploy user supervision; verify
restart, protected archive and regressions. Mission 2 UI is outside scope.

Official contracts consulted 2026-10-14:
- https://docs.polymarket.com/market-data/discover-markets
- https://docs.polymarket.com/market-data/realtime-data
- https://docs.polymarket.com/api-reference/wss/market

Gamma returns explicit v1 CTF token IDs and v2 position IDs. This initial engine
selects only explicit v1 active accepting-order markets with validated distinct
binary tokens; V2 is excluded with a reason. Discovery is a bounded liquidity
page, sorted deterministically by reported 24-hour volume then market ID.
Public WS uses `assets_ids`, market subscription and text PING every ten seconds.
No documented reliable per-book sequence exists in this contract. Receive order
is an observation order, not exchange causality or execution latency.
