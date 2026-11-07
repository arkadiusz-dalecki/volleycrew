"""Pure team selection; the caller supplies current unrounded ratings."""

from decimal import localcontext
from itertools import combinations
from random import SystemRandom
from uuid import UUID

from app.domain.rating import BASE_RATING, PRECISION  # noqa: F401


def split_teams(ratings: dict[UUID, float], mode: str, random_source=None):
    ids = sorted(ratings, key=str)
    if not 2 <= len(ids) <= 14:
        raise ValueError("Teams require 2–14 present players")
    size = len(ids) // 2
    if mode == "random":
        (random_source or SystemRandom()).shuffle(ids)
        return ids[:size], ids[size:]
    if mode != "balanced":
        raise ValueError("Unknown team mode")

    def score(side):
        other = [identifier for identifier in ids if identifier not in side]
        with localcontext() as context:
            context.prec = PRECISION
            return abs(
                sum(ratings[p] for p in side) / len(side)
                - sum(ratings[p] for p in other) / len(other)
            ), tuple(map(str, side))

    choices = combinations(ids, size)
    if len(ids) % 2 == 0:
        choices = (side for side in choices if ids[0] in side)  # remove symmetric duplicates
    best = min(choices, key=score)
    return list(best), [identifier for identifier in ids if identifier not in best]


def validate_teams(present, a, b):
    all_ids = a + b
    if (
        not 2 <= len(present) <= 14
        or not 1 <= len(a) <= 7
        or not 1 <= len(b) <= 7
        or abs(len(a) - len(b)) > 1
        or len(all_ids) != len(set(all_ids))
        or set(all_ids) != set(present)
    ):
        raise ValueError("Every present player must belong to exactly one balanced-size team")
