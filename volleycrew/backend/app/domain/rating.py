"""Volleycrew ELO v1: set share versus expectation, no display rounding in state."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

ALGORITHM = "elo-sets-v1"
PRECISION = 50
BASE_RATING = Decimal(1000)
K = Decimal(32)
SCALE = Decimal(400)


@dataclass(frozen=True)
class Outcome:
    expected_a: Decimal
    share_a: Decimal | None
    delta_a: Decimal
    delta_b: Decimal


def evaluate(mean_a: Decimal, mean_b: Decimal, sets_a: int, sets_b: int) -> Outcome:
    if type(sets_a) is not int or type(sets_b) is not int or min(sets_a, sets_b) < 0:
        raise ValueError("Sets must be non-negative integers")
    with localcontext() as context:
        context.prec = PRECISION
        expected = Decimal(1) / (1 + Decimal(10) ** ((mean_b - mean_a) / SCALE))
        if sets_a + sets_b == 0:
            return Outcome(expected, None, Decimal(0), Decimal(0))
        share = Decimal(sets_a) / Decimal(sets_a + sets_b)
        delta = K * (share - expected)
        return Outcome(expected, share, delta, -delta)


def mean(values):
    with localcontext() as context:
        context.prec = PRECISION
        return sum(values, Decimal(0)) / len(values)


def apply_delta(value, delta):
    with localcontext() as context:
        context.prec = PRECISION
        return value + delta
