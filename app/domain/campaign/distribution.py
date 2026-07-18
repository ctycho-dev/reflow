# app/domain/campaign/distribution.py
from decimal import Decimal


def equal_split(pool: int, n: int) -> list[int]:
    """
    Split `pool` (wei) equally among `n` winners as integers.

    Integer division leaves a remainder (dust): pool // n rarely divides evenly.
    The invariant that MUST hold is sum(result) == pool, because the on-chain
    distributor is funded with exactly `pool` and every wei must be claimable —
    otherwise the last claim reverts (underfunded) or tokens strand (overfunded).

    Policy: the remainder goes to the FIRST winner. The remainder is always
    < n wei (at 18 decimals, an invisible rounding fleck), so which winner
    receives it is economically meaningless; what matters is determinism and
    the exact sum. Winners must already be in their canonical (sorted) order so
    "first" is deterministic.
    """
    if n <= 0:
        raise ValueError("need at least one winner")
    if pool < 0:
        raise ValueError("pool cannot be negative")

    base = pool // n
    remainder = pool - base * n  # 0 <= remainder < n
    amounts = [base] * n
    amounts[0] += remainder

    assert sum(amounts) == pool, "split invariant violated"
    return amounts
