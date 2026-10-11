"""Official exponent-one schedule; rebates never included as receivable income."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from midas.core.models import Fee

D = Decimal
VERSION = "polymarket-fees-2026-10-11"
SOURCE = "https://docs.polymarket.com/trading/fees"


def fee_amount(q: Decimal, p: Decimal, schedule: Fee, maker: bool = False) -> Decimal:
    if not schedule.verified or schedule.exponent != 1:
        raise ValueError("Unknown or unsupported fee schedule")
    if not q.is_finite() or q < 0 or not p.is_finite() or not 0 < p < 1:
        raise ValueError("Invalid fee operands")
    if maker:
        return D(0)
    return (q * schedule.rate * p * (1 - p)).quantize(D(".00001"), rounding=ROUND_HALF_UP)


def fragmented_bound(q: Decimal, p: Decimal, rate: Decimal) -> Decimal:
    # For nearest-5dp rounding, rounded(x) <= 2*x for every x>=0.
    # Thus a sum of unknown maker fragments is bounded without assuming minimum match size.
    return (2 * q * rate * p * (1 - p)).quantize(D(".00001"), rounding=ROUND_CEILING)
