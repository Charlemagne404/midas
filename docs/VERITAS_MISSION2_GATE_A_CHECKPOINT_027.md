# Gate A checkpoint 027 — OpenAI IPO basket REST recapture

**Captured:** 2026-10-15T18:25:58.861568Z  
**Mission status:** active; no candidate qualified.

## Capture and replay

A single unauthenticated `POST /books` request returned all 14 Yes/No token books
for the previously verified seven-market OpenAI IPO NegRisk group. The response
arrived in 91 ms (38,708 bytes). The sealed study replay matched its recorded
result digest. This capture reused the existing sealed membership and on-chain
question-count evidence; it did not repeat group discovery. No order or
authenticated request was made.

- Artifact: `data/veritas-observatory/structure-studies/1792088758861568141-openai-ipo-basket-study.json`
- Artifact SHA-256: `867272ede02f571c3f26c402f03ecd96de7a189f0c63765eee4dfc1954048330`
- Artifact file SHA-256: `572a1c9b96a43dfe3491bcdb3d26cd4a551518ee94b8278482561965d5eea111`
- Result SHA-256: `0580611cea37aad99ec4d35e0a70f11a9301f1ba3eb5a8dc66697fe00557c350`
- Response SHA-256: `00acf7e35bbd08454d3d88b5631d8bdff8cfeb48777336da5cd1a9c4450b1211`

The response was complete, but its source timestamps were not fresh: maximum
source age was 31,404 ms against a 5,000 ms limit, and cross-market skew was
24,598 ms against a 250 ms limit. The REST response has no sequence field. The
short HTTP duration therefore does not establish fresh venue state.

## Economics

The complete Yes set cost $1.012 at the best asks for a conditional $1 payout,
for a gross edge of -$0.012 per set. The complete No set cost $6.021 against a
$6 protocol payout floor, for -$0.021 gross per set. All books had requested
depth and leg minimums at 5, 20, and 100 shares per outcome, but every tested
basket remained negative gross and after the fragmentation-safe fee envelope:

| Shares per outcome | Yes gross | Yes fee-safe | No gross | No fee-safe |
| ---: | ---: | ---: | ---: | ---: |
| 5 | -$0.060 | -$0.08911 | -$0.105 | -$0.12718 |
| 20 | -$0.25760 | -$0.37532 | -$0.420 | -$0.50866 |
| 100 | -$1.50916 | -$2.11498 | -$2.100 | -$2.54317 |

This is one stale market observation. It does not estimate opportunity
frequency, prove executable fills, or support any strategy or model comparison.
The no-trade baseline remains. The raw response is in the local gitignored
observatory directory; versioned lineage and limitations are in [inventory
034](VERITAS_MISSION2_RESEARCH_INVENTORY_034.json) and [research ledger H067](VERITAS_RESEARCH_LEDGER.json).

The next useful structure experiment needs independent sequence or equivalent
freshness evidence. Further REST-only recaptures are low value until that
source-quality gap changes. Scheduled observation and Director cycles remain
untouched. Mission 2 remains active.
