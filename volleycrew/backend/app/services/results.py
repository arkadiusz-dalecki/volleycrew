import json
from uuid import uuid4

from sqlalchemy import delete, func, insert, select

from app.api.errors import DomainError
from app.api.meeting_schemas import PublicPlayer
from app.api.result_schemas import (
    AdminResultView,
    HistoricalTeams,
    OutcomeView,
    PlayerRatingHistory,
    RankingPage,
    RankingPlayer,
    RatingChange,
    RatingHistoryItem,
    ResultPreview,
    ResultsPage,
    ResultSummary,
    ResultView,
    RevisionView,
)
from app.core.security import token_hash
from app.domain.rating import ALGORITHM, BASE_RATING, apply_delta
from app.domain.replay import Match, replay
from app.domain.teams import validate_teams
from app.models.auth import Player
from app.models.meetings import Meeting
from app.models.results import (
    PlayerRating,
    RatingCalculation,
    RatingEntry,
    RatingState,
    ResultMutation,
    ResultRevision,
)
from app.models.room import Attendance, AttendanceEvent, TeamMember, TeamSheet
from app.services import enrollment, room
from app.services.auth import audit


async def state_lock(db, write=False):
    return await db.scalar(
        select(RatingState)
        .where(RatingState.id == 1)
        .with_for_update(read=not write)
        .execution_options(populate_existing=True)
    )


async def current_ratings(db, ids):
    rows = (await db.scalars(select(PlayerRating).where(PlayerRating.player_id.in_(ids)))).all()
    stored = {row.player_id: row.points for row in rows}
    return {identifier: stored.get(identifier, BASE_RATING) for identifier in ids}


async def active_result(db, meeting_id):
    return await db.scalar(
        select(ResultRevision).where(
            ResultRevision.meeting_id == meeting_id, ResultRevision.active.is_(True)
        )
    )


async def members(db, sheet_id):
    rows = (
        await db.scalars(
            select(TeamMember)
            .where(TeamMember.sheet_id == sheet_id)
            .order_by(TeamMember.side, TeamMember.position)
        )
    ).all()
    return tuple(row.player_id for row in rows if row.side == "A"), tuple(
        row.player_id for row in rows if row.side == "B"
    )


async def matches(db):
    rows = (
        await db.execute(
            select(ResultRevision, Meeting, TeamMember)
            .join(Meeting, Meeting.id == ResultRevision.meeting_id)
            .join(TeamMember, TeamMember.sheet_id == ResultRevision.sheet_id)
            .where(ResultRevision.active.is_(True))
            .order_by(TeamMember.side, TeamMember.position)
        )
    ).all()
    grouped = {}
    for revision, meeting, member in rows:
        if revision.meeting_id not in grouped:
            grouped[revision.meeting_id] = (revision, meeting, [], [])
        grouped[revision.meeting_id][2 if member.side == "A" else 3].append(member.player_id)
    return [
        Match(m.id, r.id, m.starts_at, tuple(a), tuple(b), r.sets_a, r.sets_b)
        for r, m, a, b in grouped.values()
    ]


def outcome_view(calculation):
    return OutcomeView(
        mean_a=calculation.mean_a,
        mean_b=calculation.mean_b,
        expected_a=calculation.outcome.expected_a,
        share_a=calculation.outcome.share_a,
        delta_a=calculation.outcome.delta_a,
        delta_b=calculation.outcome.delta_b,
    )


async def validate_candidate(db, meeting, body, correction):
    existing = await active_result(db, meeting.id)
    if correction:
        if meeting.status != "completed" or not existing:
            raise DomainError(
                409, "result_required", "Najpierw zapisz wynik dla zatwierdzonych składów."
            )
        a, b = tuple(body.team_a), tuple(body.team_b)
        new_present = set(a + b)
        old_present = set(await room.present_ids(db, meeting))
        changes = {change.player_id: change for change in body.presence_changes}
        if len(changes) != len(body.presence_changes) or set(changes) != old_present ^ new_present:
            raise DomainError(
                422,
                "invalid_presence_changes",
                "Każda dodana lub usunięta osoba wymaga osobnej korekty obecności z powodem.",
            )
        for identifier, change in changes.items():
            if not change.reason.strip() or (
                (change.value == "present") != (identifier in new_present)
            ):
                raise DomainError(
                    422,
                    "invalid_presence_changes",
                    "Sprawdź kierunek i powód każdej korekty obecności.",
                )
        found = set((await db.scalars(select(Player.id).where(Player.id.in_(new_present)))).all())
        if found != new_present:
            raise DomainError(422, "invalid_players", "Wybierz wyłącznie istniejące profile.")
    else:
        if meeting.status != "teams_confirmed" or existing:
            raise DomainError(
                409,
                "teams_required",
                "Wynik wymaga zatwierdzonych składów. Zapisany wynik zmienia się korektą.",
            )
        sheet = await room.active_sheet(db, meeting.id)
        if (
            not sheet
            or sheet.state != "confirmed"
            or sheet.attendance_revision != meeting.attendance_revision
        ):
            raise DomainError(409, "teams_required", "Zatwierdź aktualne składy przed wynikiem.")
        a, b = await members(db, sheet.id)
        new_present = set(await room.present_ids(db, meeting))
    try:
        validate_teams(list(new_present), list(a), list(b))
    except ValueError as exc:
        raise DomainError(
            422,
            "invalid_teams",
            "Każdy obecny musi być w jednej drużynie; "
            "2–14 osób, maks.7 na stronę, różnica najwyżej 1.",
        ) from exc
    return Match(meeting.id, uuid4(), meeting.starts_at, a, b, body.sets_a, body.sets_b)


async def calculate_candidate(db, meeting, body, correction):
    candidate = await validate_candidate(db, meeting, body, correction)
    all_matches = [match for match in await matches(db) if match.meeting_id != meeting.id]
    all_matches.append(candidate)
    result = replay(all_matches)
    target = next(c for c in result[3] if c.match.meeting_id == meeting.id)
    return candidate, result, target


async def preview(db, meeting_id, body, correction=False):
    state = await state_lock(db)
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    if meeting.version != body.expected_version:
        raise DomainError(409, "version_conflict", "Spotkanie się zmieniło. Wczytaj aktualne dane.")
    _, result, target = await calculate_candidate(db, meeting, body, correction)
    people = {
        p.id: p
        for p in (await db.scalars(select(Player).where(Player.id.in_(target.before)))).all()
    }
    players = []
    for side, ids, delta in [
        ("A", target.match.team_a, target.outcome.delta_a),
        ("B", target.match.team_b, target.outcome.delta_b),
    ]:
        for identifier in ids:
            players.append(
                RatingChange(
                    player=PublicPlayer.model_validate(people[identifier]),
                    side=side,
                    before=target.before[identifier],
                    delta=delta,
                    after=apply_delta(target.before[identifier], delta),
                )
            )
    return ResultPreview(
        meeting_version=meeting.version,
        rating_version=state.version,
        sets_a=body.sets_a,
        sets_b=body.sets_b,
        outcome=outcome_view(target),
        players=players,
        recalculated_meetings=sum(
            (c.match.starts_at, c.match.meeting_id)
            >= (target.match.starts_at, target.match.meeting_id)
            for c in result[3]
        ),
    )


async def correct_presence(db, meeting, changes, actor_id, at):
    for change in changes:
        row = await db.get(Attendance, (meeting.id, change.player_id))
        if row is None:
            row = Attendance(meeting_id=meeting.id, player_id=change.player_id)
            db.add(row)
        if row.root_event_id:
            db.add(
                AttendanceEvent(
                    meeting_id=meeting.id,
                    player_id=change.player_id,
                    actor_id=actor_id,
                    kind=change.value,
                    correction_of=row.root_event_id,
                    reason=change.reason,
                    created_at=at,
                )
            )
        else:
            root = AttendanceEvent(
                id=uuid4(),
                meeting_id=meeting.id,
                player_id=change.player_id,
                actor_id=actor_id,
                kind=change.value,
                reason=change.reason,
                created_at=at,
            )
            db.add(root)
            await db.flush()
            row.root_event_id = root.id
        row.draft_state = row.confirmed_state = "present" if change.value == "present" else "absent"
    if changes:
        meeting.attendance_revision += 1
    await db.flush()


async def persist_replay(db, result, state):
    ratings, counts, entries, calculations = result
    await db.execute(delete(RatingEntry))
    await db.execute(delete(RatingCalculation))
    await db.execute(delete(PlayerRating))
    if ratings:
        await db.execute(
            insert(PlayerRating),
            [dict(player_id=p, points=value, meetings=counts[p]) for p, value in ratings.items()],
        )
    if entries:
        await db.execute(
            insert(RatingEntry),
            [
                dict(
                    meeting_id=e.match.meeting_id,
                    player_id=e.player_id,
                    result_id=e.match.result_id,
                    side=e.side,
                    before=e.before,
                    delta=e.delta,
                    after=e.after,
                )
                for e in entries
            ],
        )
    if calculations:
        await db.execute(
            insert(RatingCalculation),
            [
                dict(
                    meeting_id=c.match.meeting_id,
                    result_id=c.match.result_id,
                    **outcome_view(c).model_dump(),
                )
                for c in calculations
            ],
        )
    state.version += 1


async def save(db, meeting_id, body, actor_id, key, clock, correction=False):
    state = await state_lock(db, write=True)
    meeting = await enrollment.lock_meeting(db, meeting_id)
    digest = token_hash(str(correction) + json.dumps(body.model_dump(mode="json"), sort_keys=True))
    receipt = await db.get(ResultMutation, (actor_id, meeting_id, key))
    if receipt:
        if receipt.fingerprint != digest:
            raise DomainError(409, "idempotency_conflict", "Ten klucz dotyczy innej operacji.")
        return meeting
    if meeting.version != body.expected_version or state.version != body.expected_rating_version:
        raise DomainError(
            409,
            "version_conflict",
            "Spotkanie lub ranking się zmieniły. Pokaż nowy podgląd przed zatwierdzeniem.",
        )
    candidate, result, target = await calculate_candidate(db, meeting, body, correction)
    at = clock.now()
    old = await active_result(db, meeting_id)
    sheet = await room.active_sheet(db, meeting_id)
    if correction:
        await correct_presence(db, meeting, body.presence_changes, actor_id, at)
        sheet.state = "archived"
        await db.flush()
        meeting.team_revision += 1
        sheet = TeamSheet(
            id=uuid4(),
            meeting_id=meeting.id,
            revision=meeting.team_revision,
            attendance_revision=meeting.attendance_revision,
            state="confirmed",
            method="manual",
            created_at=at,
            confirmed_at=at,
        )
        db.add(sheet)
        await db.flush()
        await room.write_members(
            db, sheet, list(candidate.team_a), list(candidate.team_b), target.before
        )
        old.active = False
        await db.flush()
    revision = ResultRevision(
        id=candidate.result_id,
        meeting_id=meeting.id,
        revision=old.revision + 1 if old else 1,
        sheet_id=sheet.id,
        sets_a=body.sets_a,
        sets_b=body.sets_b,
        actor_id=actor_id,
        created_at=at,
        reason=body.reason if correction else None,
        active=True,
        algorithm=ALGORITHM,
    )
    db.add(revision)
    await db.flush()
    await persist_replay(db, result, state)
    meeting.status = "completed"
    meeting.version += 1
    db.add(ResultMutation(actor_id=actor_id, meeting_id=meeting_id, key=key, fingerprint=digest))
    audit(db, actor_id, "correct_result" if correction else "save_result", revision.id, at)
    await db.flush()
    return meeting


async def result_view(db, meeting, state, private=False):
    revision = await active_result(db, meeting.id)
    if not revision:
        return None
    calculation = await db.get(RatingCalculation, meeting.id)
    entries = (
        await db.scalars(
            select(RatingEntry)
            .where(RatingEntry.meeting_id == meeting.id)
            .order_by(RatingEntry.side, RatingEntry.player_id)
        )
    ).all()
    people = {
        p.id: p
        for p in (
            await db.scalars(select(Player).where(Player.id.in_([e.player_id for e in entries])))
        ).all()
    }
    history = (
        await db.scalars(
            select(ResultRevision)
            .where(ResultRevision.meeting_id == meeting.id)
            .order_by(ResultRevision.revision.desc())
        )
    ).all()
    actors = {
        p.id: p
        for p in (
            await db.scalars(select(Player).where(Player.id.in_([r.actor_id for r in history])))
        ).all()
    }
    data = dict(
        meeting_id=meeting.id,
        meeting_version=meeting.version,
        rating_version=state.version,
        starts_at=meeting.starts_at,
        revision=revision.revision,
        state="no_sets" if revision.sets_a + revision.sets_b == 0 else "played",
        sets_a=revision.sets_a,
        sets_b=revision.sets_b,
        algorithm=revision.algorithm,
        outcome=OutcomeView.model_validate(calculation, from_attributes=True),
        players=[
            RatingChange(
                player=PublicPlayer.model_validate(people[e.player_id]),
                side=e.side,
                before=e.before,
                delta=e.delta,
                after=e.after,
            )
            for e in entries
        ],
        revisions=[
            RevisionView(
                revision=r.revision,
                sets_a=r.sets_a,
                sets_b=r.sets_b,
                created_at=r.created_at,
                actor=PublicPlayer.model_validate(actors[r.actor_id]),
            )
            for r in history
        ],
    )
    if private:
        archived = (
            await db.execute(
                select(TeamMember, Player)
                .join(Player, Player.id == TeamMember.player_id)
                .where(TeamMember.sheet_id.in_([r.sheet_id for r in history]))
                .order_by(TeamMember.side, TeamMember.position)
            )
        ).all()
        squads = {
            r.revision: HistoricalTeams(
                team_a=[
                    PublicPlayer.model_validate(p)
                    for member, p in archived
                    if member.sheet_id == r.sheet_id and member.side == "A"
                ],
                team_b=[
                    PublicPlayer.model_validate(p)
                    for member, p in archived
                    if member.sheet_id == r.sheet_id and member.side == "B"
                ],
            )
            for r in history
        }
        return AdminResultView(
            **data, reasons={r.revision: r.reason for r in history if r.reason}, squads=squads
        )
    return ResultView(**data)


async def ranking(db, limit, offset):
    state = await state_lock(db)
    points = func.coalesce(PlayerRating.points, BASE_RATING)
    query = (
        select(
            Player,
            points.label("points"),
            func.coalesce(PlayerRating.meetings, 0).label("meetings"),
            func.rank().over(order_by=points.desc()).label("position"),
        )
        .outerjoin(PlayerRating, PlayerRating.player_id == Player.id)
        .order_by(points.desc(), Player.last_name, Player.first_name, Player.id)
    )
    total = await db.scalar(select(func.count()).select_from(Player))
    rows = (await db.execute(query.offset(offset).limit(limit))).all()
    return RankingPage(
        version=state.version,
        total=total,
        next_offset=offset + limit if offset + limit < total else None,
        items=[
            RankingPlayer(
                player=PublicPlayer.model_validate(p),
                points=score,
                meetings=count,
                position=position,
            )
            for p, score, count, position in rows
        ],
    )


def summary(revision, meeting, calculation):
    return dict(
        meeting_id=meeting.id,
        starts_at=meeting.starts_at,
        revision=revision.revision,
        sets_a=revision.sets_a,
        sets_b=revision.sets_b,
        state="no_sets" if revision.sets_a + revision.sets_b == 0 else "played",
        delta_a=calculation.delta_a,
        delta_b=calculation.delta_b,
    )


async def result_history(db, limit, offset):
    state = await state_lock(db)
    total = await db.scalar(
        select(func.count()).select_from(ResultRevision).where(ResultRevision.active.is_(True))
    )
    rows = (
        await db.execute(
            select(ResultRevision, Meeting, RatingCalculation)
            .join(Meeting, Meeting.id == ResultRevision.meeting_id)
            .join(RatingCalculation, RatingCalculation.meeting_id == Meeting.id)
            .where(ResultRevision.active.is_(True))
            .order_by(Meeting.starts_at.desc(), Meeting.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return ResultsPage(
        version=state.version,
        total=total,
        next_offset=offset + limit if offset + limit < total else None,
        items=[ResultSummary(**summary(r, m, c)) for r, m, c in rows],
    )


async def player_history(db, player_id, limit, offset):
    state = await state_lock(db)
    player = await db.get(Player, player_id)
    if not player:
        raise DomainError(404, "not_found", "Nie znaleziono zawodnika.")
    rating = await db.get(PlayerRating, player_id)
    total = await db.scalar(
        select(func.count()).select_from(RatingEntry).where(RatingEntry.player_id == player_id)
    )
    rows = (
        await db.execute(
            select(RatingEntry, ResultRevision, Meeting, RatingCalculation)
            .join(ResultRevision, ResultRevision.id == RatingEntry.result_id)
            .join(Meeting, Meeting.id == RatingEntry.meeting_id)
            .join(RatingCalculation, RatingCalculation.meeting_id == Meeting.id)
            .where(RatingEntry.player_id == player_id)
            .order_by(Meeting.starts_at.desc(), Meeting.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return PlayerRatingHistory(
        version=state.version,
        player=PublicPlayer.model_validate(player),
        points=rating.points if rating else BASE_RATING,
        total=total,
        next_offset=offset + limit if offset + limit < total else None,
        items=[
            RatingHistoryItem(
                **summary(r, m, c), before=e.before, delta=e.delta, after=e.after, side=e.side
            )
            for e, r, m, c in rows
        ],
    )
