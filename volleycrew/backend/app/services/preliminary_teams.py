"""Live enrollment-based teams, separate from confirmed attendance and official sheets."""

import json
from decimal import Decimal, localcontext
from uuid import UUID

from sqlalchemy import func, select

from app.api.errors import DomainError
from app.api.meeting_schemas import PublicPlayer
from app.api.room_schemas import PreliminaryTeamsView, TeamPlayer
from app.core.security import token_hash
from app.domain.rating import PRECISION
from app.domain.teams import split_teams, validate_teams
from app.models.auth import Player
from app.models.enrollment import EnrollmentEvent
from app.models.meetings import Enrollment
from app.models.room import PreliminaryTeams
from app.services import enrollment
from app.services.auth import audit
from app.services.results import current_ratings


async def roster(db, meeting):
    rows = (
        await db.execute(
            select(Enrollment, Player)
            .join(Player, Player.id == Enrollment.player_id)
            .where(
                Enrollment.meeting_id == meeting.id,
                Enrollment.declaration == "going",
                Enrollment.allocation == "seat",
                Enrollment.confirmed_term_version == meeting.term_version,
                Enrollment.reconfirmation_required.is_(False),
                Player.is_active.is_(True),
            )
            .order_by(Player.id)
        )
    ).all()
    people = {person.id: person for entry, person in rows}
    ratings = await current_ratings(db, list(people))
    # Rejoining receives a fresh queue number, so an old manual split cannot
    # reappear when exactly the same people leave and later sign up again.
    epoch = await db.scalar(
        select(func.count())
        .select_from(EnrollmentEvent)
        .where(EnrollmentEvent.meeting_id == meeting.id)
    )
    payload = {
        "term": meeting.term_version,
        "enrollment_epoch": epoch,
        "players": [
            (str(person.id), entry.queue_number, str(ratings[person.id])) for entry, person in rows
        ],
    }
    token = token_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return people, ratings, token


async def choice(db, meeting):
    people, ratings, token = await roster(db, meeting)
    stored = await db.get(PreliminaryTeams, meeting.id)
    method, a, b = "balanced", [], []
    if len(people) >= 2:
        if stored and stored.roster_token == token:
            try:
                a, b = (
                    [UUID(value) for value in stored.team_a],
                    [UUID(value) for value in stored.team_b],
                )
                validate_teams(list(people), a, b)
                method = stored.method
            except (ValueError, TypeError):
                a, b = split_teams(ratings, "balanced")
        else:
            a, b = split_teams(ratings, "balanced")
    return people, ratings, token, stored, method, a, b


def average(ids, ratings):
    with localcontext() as context:
        context.prec = PRECISION
        return float(sum((ratings[p] for p in ids), Decimal(0)) / len(ids)) if ids else 0


async def view(db, meeting):
    if meeting.status != "scheduled" or meeting.attendance_confirmed_at:
        return None
    people, ratings, token, stored, method, a, b = await choice(db, meeting)

    def side(ids):
        return [
            TeamPlayer(
                player=PublicPlayer.model_validate(people[p]), position=i, rating=float(ratings[p])
            )
            for i, p in enumerate(ids)
        ]

    return PreliminaryTeamsView(
        meeting_id=meeting.id,
        roster_token=token,
        revision=stored.revision if stored else 0,
        method=method,
        participant_count=len(people),
        team_a=side(a),
        team_b=side(b),
        average_a=average(a, ratings),
        average_b=average(b, ratings),
    )


async def save(db, meeting, body, actor_id, clock):
    if meeting.status != "scheduled" or meeting.attendance_confirmed_at:
        raise DomainError(
            409, "preview_closed", "Obecność została już zatwierdzona. Użyj panelu drużyn."
        )
    people, ratings, token, stored, _, _, _ = await choice(db, meeting)
    if body.roster_token != token or body.revision != (stored.revision if stored else 0):
        raise DomainError(
            409,
            "preview_changed",
            "Lista lub podział zmieniły się. Wczytujemy aktualne boisko; ponów zmianę.",
        )
    try:
        a, b = (
            (body.team_a, body.team_b) if body.mode == "manual" else split_teams(ratings, body.mode)
        )
        validate_teams(list(people), a, b)
    except ValueError as exc:
        raise DomainError(
            422,
            "invalid_teams",
            "Do podziału potrzeba 2–14 zapisanych osób, każdej dokładnie raz, "
            "najwyżej 7 na stronę.",
        ) from exc
    if not stored:
        stored = PreliminaryTeams(meeting_id=meeting.id, revision=0)
        db.add(stored)
    stored.roster_token = token
    stored.revision += 1
    stored.method = body.mode
    stored.team_a, stored.team_b = list(map(str, a)), list(map(str, b))
    stored.actor_id, stored.updated_at = actor_id, enrollment.current_time(clock)
    audit(db, actor_id, "preview_teams", meeting.id, stored.updated_at)
    await db.flush()
    return await view(db, meeting)


async def for_present(db, meeting, present, ratings):
    _, current, _, _, method, a, b = await choice(db, meeting)
    if set(a + b) == set(present) and all(current[p] == ratings[p] for p in present):
        return a, b, method
    a, b = split_teams(ratings, "balanced")
    return a, b, "balanced"
