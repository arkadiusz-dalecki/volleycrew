from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.rating import BASE_RATING, Outcome, apply_delta, evaluate, mean


@dataclass(frozen=True)
class Match:
    meeting_id: UUID
    result_id: UUID
    starts_at: datetime
    team_a: tuple[UUID, ...]
    team_b: tuple[UUID, ...]
    sets_a: int
    sets_b: int


@dataclass(frozen=True)
class Entry:
    match: Match
    player_id: UUID
    side: str
    before: Decimal
    delta: Decimal
    after: Decimal


@dataclass(frozen=True)
class Calculation:
    match: Match
    mean_a: Decimal
    mean_b: Decimal
    outcome: Outcome
    before: dict[UUID, Decimal]


def replay(matches: list[Match]):
    ratings, counts, entries, calculations = {}, {}, [], []
    for match in sorted(matches, key=lambda m: (m.starts_at, m.meeting_id)):
        before = {
            identifier: ratings.get(identifier, BASE_RATING)
            for identifier in match.team_a + match.team_b
        }
        mean_a, mean_b = (
            mean([before[p] for p in match.team_a]),
            mean([before[p] for p in match.team_b]),
        )
        result = evaluate(mean_a, mean_b, match.sets_a, match.sets_b)
        calculations.append(Calculation(match, mean_a, mean_b, result, before))
        if result.share_a is None:
            continue
        for side, players, delta in [
            ("A", match.team_a, result.delta_a),
            ("B", match.team_b, result.delta_b),
        ]:
            for player in players:
                after = apply_delta(before[player], delta)
                ratings[player] = after
                counts[player] = counts.get(player, 0) + 1
                entries.append(Entry(match, player, side, before[player], delta, after))
    return ratings, counts, entries, calculations
