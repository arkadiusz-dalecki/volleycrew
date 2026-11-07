import json
from uuid import uuid4

from sqlalchemy import delete, func, select, text

from app.api.errors import DomainError
from app.api.meeting_schemas import PublicPlayer
from app.api.room_schemas import (
    AttendancePlayer,
    AttendanceView,
    CorrectionView,
    HistoryItem,
    HistoryPage,
    ReservedPlayer,
    TeamPlayer,
    TeamsView,
)
from app.core.security import token_hash
from app.domain.teams import split_teams, validate_teams
from app.models.auth import Player
from app.models.meetings import Enrollment, Meeting
from app.models.room import Attendance, AttendanceEvent, RoomMutation, TeamMember, TeamSheet
from app.services import enrollment
from app.services.auth import audit


async def begin(db, meeting_id, actor_id, action, body, key, clock):
    meeting = await enrollment.lock_meeting(db, meeting_id)
    at = enrollment.current_time(clock)
    digest = token_hash(action + json.dumps(body.model_dump(mode="json"), sort_keys=True))
    previous = await db.get(RoomMutation, (actor_id, meeting_id, key))
    if previous:
        if previous.fingerprint != digest:
            raise DomainError(409, "idempotency_conflict", "Ten klucz dotyczy innej operacji.")
        return meeting, at, True
    if meeting.version != body.expected_version:
        raise DomainError(
            409,
            "version_conflict",
            "Dane zmieniły się w innej karcie. Odśwież stan przed zatwierdzeniem.",
        )
    if meeting.status == "cancelled":
        raise DomainError(
            409, "meeting_cancelled", "Odwołane spotkanie nie ma obsługi obecności ani drużyn."
        )
    db.add(RoomMutation(actor_id=actor_id, meeting_id=meeting_id, key=key, fingerprint=digest))
    return meeting, at, False


def started(meeting, at):
    if at < meeting.starts_at:
        raise DomainError(
            409, "not_started", "Obecność można zatwierdzić od rozpoczęcia spotkania."
        )


def editable_presence(meeting):
    if meeting.status == "teams_confirmed":
        raise DomainError(
            409, "teams_locked", "Najpierw otwórz składy do poprawy z podaniem powodu."
        )
    if meeting.status == "completed":
        raise DomainError(
            409,
            "historical_roster_locked",
            "Zmiana historycznych składów wymaga obsługi korekty wyniku.",
        )


async def candidates(db, meeting):
    pairs = await enrollment.entries(db, meeting)
    expected = {
        entry.player_id
        for entry, _ in pairs
        if entry.declaration == "going"
        and entry.allocation == "seat"
        and entry.confirmed_term_version == meeting.term_version
    }
    rows = {
        row.player_id: row
        for row in (
            await db.scalars(select(Attendance).where(Attendance.meeting_id == meeting.id))
        ).all()
    }
    rows = {
        identifier: row
        for identifier, row in rows.items()
        if identifier in expected or row.confirmed_state is not None
    }
    ids = expected | rows.keys()
    people = {
        person.id: person
        for person in (await db.scalars(select(Player).where(Player.id.in_(ids)))).all()
    }
    return expected, rows, people, pairs


async def attendance_view(db, meeting, at):
    _, rows, people, pairs = await candidates(db, meeting)
    occupied = sum(
        entry.declaration == "going" and entry.allocation in {"seat", "reserved"}
        for entry, _ in pairs
    )
    players = [
        AttendancePlayer(
            player=PublicPlayer.model_validate(person),
            draft_state=rows[person.id].draft_state if person.id in rows else "unknown",
            confirmed_state=rows[person.id].confirmed_state if person.id in rows else None,
            event_id=rows[person.id].root_event_id if person.id in rows else None,
        )
        for person in sorted(people.values(), key=lambda p: (p.first_name, p.last_name, str(p.id)))
    ]
    reservations = [
        ReservedPlayer(player=PublicPlayer.model_validate(person), kind=entry.reservation_kind)
        for entry, person in pairs
        if entry.declaration == "going" and entry.allocation == "reserved"
    ]
    return AttendanceView(
        meeting_id=meeting.id,
        version=meeting.version,
        status=meeting.status,
        attendance_revision=meeting.attendance_revision,
        confirmed_at=meeting.attendance_confirmed_at,
        can_confirm=at >= meeting.starts_at
        and meeting.status == "scheduled"
        and meeting.attendance_confirmed_at is None,
        players=players,
        reservations=reservations,
        free_count=max(0, meeting.capacity - occupied),
    )


async def save_attendance(db, meeting, body):
    if meeting.status != "scheduled" or meeting.attendance_confirmed_at:
        raise DomainError(
            409, "attendance_locked", "Zatwierdzoną obecność zmienia się korektą z powodem."
        )
    expected, rows, _, _ = await candidates(db, meeting)
    ids = [item.player_id for item in body.players]
    if len(ids) != len(set(ids)) or set(ids) != expected | rows.keys():
        raise DomainError(
            409, "attendance_changed", "Lista zawodników się zmieniła. Sprawdź aktualny szkic."
        )
    for item in body.players:
        row = rows.get(item.player_id) or await db.get(Attendance, (meeting.id, item.player_id))
        if row is None:
            row = Attendance(meeting_id=meeting.id, player_id=item.player_id)
            db.add(row)
        row.draft_state = item.state
    meeting.version += 1


async def archive_draft(db, meeting):
    sheet = await active_sheet(db, meeting.id)
    if sheet:
        sheet.state = "archived"
        await db.flush()


async def confirm_attendance(db, meeting, actor_id, at):
    started(meeting, at)
    if meeting.status != "scheduled" or meeting.attendance_confirmed_at:
        raise DomainError(
            409, "attendance_locked", "Obecność została już zatwierdzona. Użyj korekty."
        )
    expected, rows, _, pairs = await candidates(db, meeting)
    if any(
        identifier not in rows or rows[identifier].draft_state == "unknown"
        for identifier in expected
    ) or any(row.draft_state == "unknown" for row in rows.values()):
        raise DomainError(
            422, "attendance_incomplete", "Oznacz każdą osobę jako obecną albo nieobecną."
        )
    if sum(row.draft_state == "present" for row in rows.values()) > meeting.capacity:
        raise DomainError(
            409, "capacity_conflict", "Na spotkaniu może być najwyżej 14 obecnych osób."
        )
    for row in rows.values():
        row.confirmed_state = row.draft_state
        if row.player_id in expected:
            history = AttendanceEvent(
                id=uuid4(),
                meeting_id=meeting.id,
                player_id=row.player_id,
                actor_id=actor_id,
                kind="present" if row.draft_state == "present" else "no_show",
                created_at=at,
            )
            db.add(history)
            await db.flush()
            row.root_event_id = history.id
    # No-show is a history entry, not a permanent claim on a place on the court.
    for entry, _ in pairs:
        if (
            entry.player_id in rows
            and rows[entry.player_id].confirmed_state == "absent"
            and entry.allocation == "seat"
        ):
            entry.allocation, entry.confirmed_term_version = "none", None
    await db.flush()
    await enrollment.rebalance(db, meeting, actor_id, at)
    meeting.attendance_revision += 1
    meeting.attendance_confirmed_at = at
    meeting.status = "attendance_checked"
    meeting.version += 1
    audit(db, actor_id, "confirm_attendance", meeting.id, at)


async def admit(db, meeting, player_id, actor_id, at):
    started(meeting, at)
    editable_presence(meeting)
    person = await db.get(Player, player_id)
    if person is None or not person.is_active:
        raise DomainError(404, "not_found", "Wybierz istniejący, niezablokowany profil.")
    _, rows, _, pairs = await candidates(db, meeting)
    if (
        player_id in rows
        and rows[player_id].confirmed_state == "absent"
        and rows[player_id].root_event_id
    ):
        raise DomainError(409, "correction_required", "Spóźnionego przywróć korektą z powodem.")
    entry = next((e for e, _ in pairs if e.player_id == player_id), None)
    if (
        entry
        and entry.allocation == "seat"
        and entry.confirmed_term_version == meeting.term_version
    ):
        raise DomainError(409, "already_enrolled", "Ta osoba jest już na liście obecności.")
    own_reservation = entry and entry.declaration == "going" and entry.allocation == "reserved"
    occupied = sum(
        e.declaration == "going" and e.allocation in {"seat", "reserved"} for e, _ in pairs
    )
    if not own_reservation and occupied >= meeting.capacity:
        raise DomainError(409, "no_free_seat", "Nie ma wolnego, niezarezerwowanego miejsca.")
    if entry is None:
        entry = Enrollment(
            meeting_id=meeting.id,
            player_id=player_id,
            declaration="going",
            allocation="none",
            declared_at=at,
        )
        db.add(entry)
    elif not own_reservation:
        entry.declared_at = at
        entry.queue_number = await db.scalar(
            text("SELECT nextval(pg_get_serial_sequence('enrollments','queue_number'))")
        )
    offer = await enrollment.active_offer(db, meeting.id, player_id)
    if offer:
        offer.state, offer.responded_at, offer.created_by = "accepted", at, actor_id
    entry.declaration, entry.allocation, entry.reservation_kind = "going", "seat", None
    entry.confirmed_term_version, entry.reconfirmation_required = meeting.term_version, False
    entry.accepted_late_offer = False
    row = rows.get(player_id) or await db.get(Attendance, (meeting.id, player_id))
    if row is None:
        row = Attendance(meeting_id=meeting.id, player_id=player_id)
        db.add(row)
    row.draft_state = "present"
    if meeting.attendance_confirmed_at:
        row.confirmed_state = "present"
        history = AttendanceEvent(
            id=uuid4(),
            meeting_id=meeting.id,
            player_id=player_id,
            actor_id=actor_id,
            kind="present",
            created_at=at,
        )
        db.add(history)
        await db.flush()
        row.root_event_id = history.id
        meeting.attendance_revision += 1
        await archive_draft(db, meeting)
    enrollment.event(db, meeting, player_id, actor_id, "admitted_on_site", at)
    meeting.version += 1


async def release_reservation(db, meeting, player_id, actor_id, at):
    started(meeting, at)
    editable_presence(meeting)
    entry = await db.scalar(
        select(Enrollment).where(
            Enrollment.meeting_id == meeting.id, Enrollment.player_id == player_id
        )
    )
    if not entry or entry.allocation != "reserved":
        raise DomainError(409, "no_reservation", "Ta osoba nie ma oczekującej rezerwacji.")
    await enrollment.revoke_offer(db, meeting, entry, actor_id, at)
    entry.declaration, entry.allocation, entry.reservation_kind = "withdrawn", "none", None
    entry.reconfirmation_required, entry.confirmed_term_version = False, None
    enrollment.event(db, meeting, player_id, actor_id, "reservation_released_on_site", at)
    await db.flush()
    await enrollment.rebalance(db, meeting, actor_id, at)
    meeting.version += 1


async def correct(db, meeting, body, actor_id, at):
    source = await db.get(AttendanceEvent, body.event_id)
    if source is None or source.meeting_id != meeting.id or source.correction_of:
        raise DomainError(404, "not_found", "Nie znaleziono źródłowego wpisu historii.")
    if source.source_enrollment_event_id:
        if body.value not in {
            "normal_cancellation",
            "late_cancellation",
            "late_offer_exception",
            "excused",
        }:
            raise DomainError(
                422, "invalid_correction", "Obecnego zawodnika dopisz osobno na sali."
            )
    else:
        if body.value not in {"present", "no_show", "excused"}:
            raise DomainError(
                422, "invalid_correction", "Wybierz obecność, nieobecność albo usprawiedliwienie."
            )
        row = await db.get(Attendance, (meeting.id, source.player_id))
        new_state = "present" if body.value == "present" else "absent"
        if row.confirmed_state != new_state:
            editable_presence(meeting)
            if new_state == "present":
                person = await db.get(Player, source.player_id)
                if not person.is_active:
                    raise DomainError(
                        409, "profile_blocked", "Nie można dopisać zablokowanego profilu."
                    )
                pairs = await enrollment.entries(db, meeting)
                occupied = sum(
                    e.declaration == "going" and e.allocation in {"seat", "reserved"}
                    for e, _ in pairs
                )
                own_entry = next(e for e, _ in pairs if e.player_id == source.player_id)
                if (
                    own_entry.allocation not in {"seat", "reserved"}
                    and occupied >= meeting.capacity
                ):
                    raise DomainError(
                        409, "no_free_seat", "Miejsce zostało już zajęte lub zarezerwowane."
                    )
                await enrollment.revoke_offer(db, meeting, own_entry, actor_id, at)
                own_entry.allocation, own_entry.reservation_kind = "seat", None
                own_entry.declaration, own_entry.confirmed_term_version = (
                    "going",
                    meeting.term_version,
                )
                own_entry.reconfirmation_required = False
            else:
                own_entry = await db.scalar(
                    select(Enrollment).where(
                        Enrollment.meeting_id == meeting.id,
                        Enrollment.player_id == source.player_id,
                    )
                )
                if own_entry:
                    own_entry.allocation, own_entry.reservation_kind = "none", None
                    own_entry.confirmed_term_version = None
            row.draft_state, row.confirmed_state = new_state, new_state
            await db.flush()
            await enrollment.rebalance(db, meeting, actor_id, at)
            meeting.attendance_revision += 1
            await archive_draft(db, meeting)
    db.add(
        AttendanceEvent(
            meeting_id=meeting.id,
            player_id=source.player_id,
            actor_id=actor_id,
            kind=body.value,
            correction_of=source.id,
            reason=body.reason,
            created_at=at,
        )
    )
    audit(db, actor_id, "correct_attendance_history", source.id, at)
    meeting.version += 1


async def active_sheet(db, meeting_id):
    return await db.scalar(
        select(TeamSheet).where(
            TeamSheet.meeting_id == meeting_id, TeamSheet.state.in_(["draft", "confirmed"])
        )
    )


async def present_ids(db, meeting):
    return list(
        (
            await db.scalars(
                select(Attendance.player_id)
                .where(Attendance.meeting_id == meeting.id, Attendance.confirmed_state == "present")
                .order_by(Attendance.player_id)
            )
        ).all()
    )


async def generate(db, meeting, mode, actor_id, at, random_source=None):
    if meeting.status != "attendance_checked" or not meeting.attendance_confirmed_at:
        raise DomainError(
            409,
            "attendance_required",
            "Najpierw zatwierdź faktyczną obecność; zatwierdzone składy otwórz do poprawy.",
        )
    ids = await present_ids(db, meeting)
    from app.services.results import current_ratings

    ratings = await current_ratings(db, ids)
    try:
        a, b = split_teams(ratings, mode, random_source)
    except ValueError as exc:
        raise DomainError(
            422, "invalid_team_size", "Do podziału potrzeba od 2 do 14 obecnych osób."
        ) from exc
    await archive_draft(db, meeting)
    meeting.team_revision += 1
    sheet = TeamSheet(
        id=uuid4(),
        meeting_id=meeting.id,
        revision=meeting.team_revision,
        attendance_revision=meeting.attendance_revision,
        state="draft",
        method=mode,
        created_at=at,
    )
    db.add(sheet)
    await db.flush()
    await write_members(db, sheet, a, b, ratings)
    meeting.version += 1
    audit(db, actor_id, "generate_teams", sheet.id, at)


async def write_members(db, sheet, a, b, ratings=None):
    if ratings is None:
        from app.services.results import current_ratings

        ratings = await current_ratings(db, a + b)
    await db.execute(delete(TeamMember).where(TeamMember.sheet_id == sheet.id))
    for side, ids in [("A", a), ("B", b)]:
        for position, identifier in enumerate(ids):
            db.add(
                TeamMember(
                    sheet_id=sheet.id,
                    player_id=identifier,
                    side=side,
                    position=position,
                    rating_snapshot=ratings[identifier],
                )
            )
    await db.flush()


async def edit_teams(db, meeting, body):
    sheet = await active_sheet(db, meeting.id)
    if meeting.status != "attendance_checked" or not sheet or sheet.state != "draft":
        raise DomainError(
            409, "teams_locked", "Wygeneruj szkic albo otwórz zatwierdzone składy do poprawy."
        )
    ids = await present_ids(db, meeting)
    try:
        validate_teams(ids, body.team_a, body.team_b)
    except ValueError as exc:
        raise DomainError(
            422,
            "invalid_teams",
            "Każdy obecny musi być w jednej drużynie, maks. 7 na stronę i różnica najwyżej 1.",
        ) from exc
    if sheet.attendance_revision != meeting.attendance_revision:
        raise DomainError(
            409, "attendance_changed", "Obecność się zmieniła. Wygeneruj nowy podział."
        )
    await write_members(db, sheet, body.team_a, body.team_b)
    sheet.method = "manual"
    meeting.version += 1


async def confirm_teams(db, meeting, actor_id, at):
    sheet = await active_sheet(db, meeting.id)
    if meeting.status != "attendance_checked" or not sheet or sheet.state != "draft":
        raise DomainError(409, "teams_locked", "Brakuje aktualnego szkicu do zatwierdzenia.")
    members = (await db.scalars(select(TeamMember).where(TeamMember.sheet_id == sheet.id))).all()
    ids = await present_ids(db, meeting)
    try:
        validate_teams(
            ids,
            [m.player_id for m in members if m.side == "A"],
            [m.player_id for m in members if m.side == "B"],
        )
    except ValueError as exc:
        raise DomainError(
            409, "attendance_changed", "Obecność się zmieniła. Popraw podział."
        ) from exc
    if sheet.attendance_revision != meeting.attendance_revision:
        raise DomainError(409, "attendance_changed", "Szkic dotyczy poprzedniej wersji obecności.")
    sheet.state, sheet.confirmed_at = "confirmed", at
    meeting.status = "teams_confirmed"
    meeting.version += 1
    audit(db, actor_id, "confirm_teams", sheet.id, at)


async def reopen(db, meeting, actor_id, at, reason):
    if meeting.status != "teams_confirmed":
        raise DomainError(
            409, "teams_locked", "Można otworzyć wyłącznie składy przed zapisaniem wyniku."
        )
    old = await active_sheet(db, meeting.id)
    old.state = "archived"
    await db.flush()
    meeting.team_revision += 1
    new = TeamSheet(
        id=uuid4(),
        meeting_id=meeting.id,
        revision=meeting.team_revision,
        attendance_revision=meeting.attendance_revision,
        state="draft",
        method=old.method,
        created_at=at,
    )
    db.add(new)
    await db.flush()
    members = (
        await db.scalars(
            select(TeamMember)
            .where(TeamMember.sheet_id == old.id)
            .order_by(TeamMember.side, TeamMember.position)
        )
    ).all()
    await write_members(
        db,
        new,
        [m.player_id for m in members if m.side == "A"],
        [m.player_id for m in members if m.side == "B"],
    )
    meeting.status = "attendance_checked"
    meeting.version += 1
    audit(db, actor_id, "reopen_teams", old.id, at, {"reason": reason})


async def teams_view(db, meeting, private=False):
    sheet = await active_sheet(db, meeting.id)
    if not sheet or (
        not private
        and (sheet.state != "confirmed" or meeting.status not in {"teams_confirmed", "completed"})
    ):
        return None
    rows = (
        await db.execute(
            select(TeamMember, Player)
            .join(Player, Player.id == TeamMember.player_id)
            .where(TeamMember.sheet_id == sheet.id)
            .order_by(TeamMember.side, TeamMember.position)
        )
    ).all()
    a = [
        TeamPlayer(
            player=PublicPlayer.model_validate(p), position=m.position, rating=m.rating_snapshot
        )
        for m, p in rows
        if m.side == "A"
    ]
    b = [
        TeamPlayer(
            player=PublicPlayer.model_validate(p), position=m.position, rating=m.rating_snapshot
        )
        for m, p in rows
        if m.side == "B"
    ]
    return TeamsView(
        meeting_id=meeting.id,
        version=meeting.version,
        revision=sheet.revision,
        state=sheet.state,
        method=sheet.method,
        team_a=a,
        team_b=b,
        average_a=sum(p.rating for p in a) / len(a),
        average_b=sum(p.rating for p in b) / len(b),
    )


async def history(db, player_id, limit, offset):
    total = await db.scalar(
        select(func.count())
        .select_from(AttendanceEvent)
        .where(AttendanceEvent.player_id == player_id, AttendanceEvent.correction_of.is_(None))
    )
    roots = (
        await db.scalars(
            select(AttendanceEvent)
            .where(AttendanceEvent.player_id == player_id, AttendanceEvent.correction_of.is_(None))
            .order_by(AttendanceEvent.sequence.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    result = []
    for root in roots:
        meeting = await db.get(Meeting, root.meeting_id)
        actor = await db.get(Player, root.actor_id)
        changes = (
            await db.scalars(
                select(AttendanceEvent)
                .where(AttendanceEvent.correction_of == root.id)
                .order_by(AttendanceEvent.sequence)
            )
        ).all()
        corrections = [
            CorrectionView(
                id=c.id,
                kind=c.kind,
                reason=c.reason,
                actor=PublicPlayer.model_validate(await db.get(Player, c.actor_id)),
                created_at=c.created_at,
            )
            for c in changes
        ]
        result.append(
            HistoryItem(
                id=root.id,
                meeting_id=meeting.id,
                meeting_version=meeting.version,
                starts_at=meeting.starts_at,
                original_kind=root.kind,
                source_reason=root.reason,
                current_kind=changes[-1].kind if changes else root.kind,
                created_at=root.created_at,
                actor=PublicPlayer.model_validate(actor),
                corrections=corrections,
            )
        )
    return HistoryPage(
        items=result, total=total, next_offset=offset + limit if offset + limit < total else None
    )
