# Market simulation and economic assumptions

Three existing execution presets remain available: optimistic (zero modeled transport
latency/full depth), standard (seeded jitter/80% modeled depth), and conservative
(longer delay/50% depth/adverse ticks). They are assumptions, not empirical exchange
calibrations. Arbitrage legs submit, match and acknowledge independently.

The venue accepts marketable limit orders with legacy IOC, FAK and FOK. FAK/IOC consume
executable depth and expire the remainder. FOK checks whole-order executable depth
before any inventory/depth mutation and otherwise releases the entire reservation.
GTC exists in the venue for legacy scenarios; the autonomous Laboratory broker selects
IOC/FAK/FOK. Full and partial fills walk multiple levels, apply modeled fees/rounding,
and consume modeled liquidity. Repeated snapshots do not grant unlimited reusable depth.

Scheduled market events replace depth or metadata, allowing withdrawal, arrival,
price movement, spread changes and pauses. The venue independently rechecks active
market state between submission and match. Invalid/unsequenced data fails closed.
Older exchange snapshots cannot overwrite newer observed or venue state.

Observation transport, strategy processing, submission, exchange processing and
acknowledgment delays are separate. Submission jitter is seeded. Scheduled cancellation
and expiration use production accounting; cancellation arrival can precede or follow
matching. At the same timestamp/priority, insertion order is authoritative; a previously
scheduled match can win the cancellation race. Lost acknowledgment does not cause
blind order resubmission. Duplicate action processing and conflicting financial IDs
are tested separately.

Network/failure families are deliberately limited models: `network_partition` and
`uncertain_order` suppress acknowledgments, not an emulation of TCP or a fully disconnected
matching service. Sequence mutation also combines withdrawal, pause, cancellation,
expiration and duplicate-action faults. Physical broker process termination and SQL
recovery remain covered by the existing Milestone 2 integration tests.

A confirmed settlement event is the only automatic path from acquired inventory to
spendable virtual proceeds. There is no automatic complete-set merge. Unresolved
positions retain their basis, inventory and lockup through the horizon. Advancing time
past an oracle announcement alone cannot invent spendable cash. Historical datasets
never receive synthetic terminal payouts. Live settlement ingestion remains the
existing finalized-evidence implementation; no new live redemption evidence is claimed.

Financing integrates `(reserved + locked) × elapsed virtual milliseconds` using the
left-hand portfolio state. Per-fill operating and per-settlement redemption costs,
and a collateral proceeds haircut, form a separately labeled analytical overlay.
It can turn favorable gross fixture results negative. It does not debit the broker
ledger or change ongoing risk admission, and it is not a net mark-to-market return on
unresolved holdings. Open inventory, hypothetical marks and gross settled virtual P&L
are reported separately. Gas/adapter costs, economic parity and empirical fill priority
remain unresolved, so all Laboratory returns remain economically unverified.

Known limitations: no calibrated queue competition, exchange settlement failures,
passive-maker strategy, automatic unmatched-leg rescue, full CTF/pUSD adapter verification,
partial complete-set merge lifecycle, or guaranteed fill reconstruction from public books.
[Official lifecycle](https://docs.polymarket.com/concepts/order-lifecycle),
[fees](https://docs.polymarket.com/trading/fees) and
[position operations](https://docs.polymarket.com/trading/positions/manage) establish
public semantics; the simulator does not claim exact internal Polymarket mechanics.
