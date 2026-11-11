"""Allocation mutations run in the caller's transaction under the same Meeting row lock."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError
from app.core.clock import Clock
from app.core.security import token_hash
from app.models.auth import Player
from app.models.enrollment import EnrollmentEvent, EnrollmentMutation, SeatOffer
from app.models.meetings import Enrollment, Meeting

PRIORITY = {"founder": 0, "player": 1, "guest": 2}
ACTIVE_OFFERS = ("reserved", "pending")


def current_time(source: datetime | Clock) -> datetime:
    return source if isinstance(source, datetime) else source.now()


def event(db, meeting, player_id, actor_id, kind, at, **details):
    from app.models.room import AttendanceEvent

    source = EnrollmentEvent(
        id=uuid4(),
        meeting_id=meeting.id,
        player_id=player_id,
        actor_id=actor_id,
        kind=kind,
        created_at=at,
        details=details,
    )
    db.add(source)
    classification = {
        "normal": "normal_cancellation",
        "late": "late_cancellation",
        "late_offer_exception": "late_offer_exception",
    }.get(details.get("cancellation_kind"))
    if kind == "withdrawn" and classification:
        db.add(
            AttendanceEvent(
                id=source.id,
                meeting_id=meeting.id,
                player_id=player_id,
                actor_id=actor_id,
                kind=classification,
                source_enrollment_event_id=source.id,
                source_enrollment_event=source,
                created_at=at,
            )
        )


async def lock_meeting(db: AsyncSession, meeting_id: UUID) -> Meeting:
    row = await db.scalar(
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.deleted_at:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    return row


def check_open(meeting: Meeting, term_version: int, at: datetime):
    if term_version != meeting.term_version:
        raise DomainError(
            409,
            "term_changed",
            "Termin spotkania się zmienił. Odśwież widok i potwierdź aktualny termin.",
        )
    if meeting.status != "scheduled" or at >= meeting.starts_at:
        raise DomainError(409, "enrollment_closed", "Zapisy na ten termin nie są dostępne.")


async def entries(db, meeting):
    return list(
        (
            await db.execute(
                select(Enrollment, Player)
                .join(Player, Player.id == Enrollment.player_id)
                .where(Enrollment.meeting_id == meeting.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )


def order(pair):
    entry, player = pair
    return PRIORITY[player.priority_status], entry.declared_at, entry.queue_number


def waiting_order(pairs):
    # Protected reservations stay ahead of new arrivals; priorities only order unreserved waiters.
    return sorted(
        (
            pair
            for pair in pairs
            if pair[0].declaration == "going"
            and pair[0].allocation in {"reserved", "waitlist"}
            and pair[0].reservation_kind != "reconfirmation"
        ),
        key=lambda pair: (0 if pair[0].allocation == "reserved" else 1, *order(pair)),
    )


async def active_offer(db, meeting_id, player_id):
    return await db.scalar(
        select(SeatOffer).where(
            SeatOffer.meeting_id == meeting_id,
            SeatOffer.player_id == player_id,
            SeatOffer.state.in_(ACTIVE_OFFERS),
        )
    )


async def revoke_offer(db, meeting, entry, actor_id, at):
    offer = await active_offer(db, meeting.id, entry.player_id)
    if offer:
        offer.state, offer.responded_at = "revoked", at
        event(db, meeting, entry.player_id, actor_id, "offer_revoked", at, offer_id=str(offer.id))


async def rebalance(db, meeting, actor_id, at, newcomer_id=None, allow_displace=False):
    from app.models.room import Attendance

    pairs = await entries(db, meeting)
    absent = set(
        (
            await db.scalars(
                select(Attendance.player_id).where(
                    Attendance.meeting_id == meeting.id, Attendance.confirmed_state == "absent"
                )
            )
        ).all()
    )
    active = [
        (entry, player)
        for entry, player in pairs
        if entry.declaration == "going" and player.is_active and entry.player_id not in absent
    ]
    fixed = [entry for entry, _ in active if entry.allocation == "reserved"]
    eligible = [(entry, player) for entry, player in active if entry.allocation != "reserved"]
    slots = meeting.capacity - len(fixed)
    if not allow_displace or at >= meeting.starts_at - timedelta(hours=24):
        seats = [entry for entry, _ in eligible if entry.allocation == "seat"]
        choices = [
            entry
            for entry, _ in sorted(
                (pair for pair in eligible if pair[0].allocation != "seat"), key=order
            )
        ][: max(0, slots - len(seats))]
        selected = {entry.player_id for entry in [*seats, *choices]}
    else:
        selected = {entry.player_id for entry, _ in sorted(eligible, key=order)[: max(0, slots)]}
    for entry, _ in eligible:
        previous = entry.allocation
        if entry.player_id not in selected:
            entry.allocation, entry.reservation_kind = "waitlist", None
            entry.confirmed_term_version = None
            entry.accepted_late_offer = False
        elif previous == "seat":
            continue
        elif entry.player_id == newcomer_id and previous == "none":
            entry.allocation, entry.reservation_kind = "seat", None
            entry.confirmed_term_version = meeting.term_version
        else:
            # A waitlist entry can only reserve a seat; accepting the proposal is separate.
            entry.allocation, entry.reservation_kind = "reserved", "offer"
            entry.confirmed_term_version = None
            offer = SeatOffer(
                meeting_id=meeting.id,
                player_id=entry.player_id,
                enrollment_sequence=entry.queue_number,
                term_version=meeting.term_version,
                state="reserved",
                reserved_at=at,
            )
            db.add(offer)
        if previous != entry.allocation:
            event(
                db,
                meeting,
                entry.player_id,
                actor_id,
                "allocation_changed",
                at,
                previous=previous,
                allocation=entry.allocation,
            )
    await db.flush()
    occupied = sum(entry.allocation in {"seat", "reserved"} for entry, _ in active)
    if occupied > meeting.capacity:
        raise DomainError(409, "capacity_conflict", "Lista miejsc wymaga odświeżenia.")


def cancellation_kind(meeting, entry, at):
    if (
        not entry
        or entry.declaration != "going"
        or entry.allocation != "seat"
        or entry.confirmed_term_version != meeting.term_version
    ):
        return "none"
    if at <= meeting.starts_at - timedelta(hours=24):
        return "normal"
    return "late_offer_exception" if entry.accepted_late_offer else "late"


async def declare(
    db, meeting_id, player, declaration, term_version, at, key, acknowledge_late=False
):
    meeting = await lock_meeting(db, meeting_id)
    at = current_time(at)
    if not player.is_active:
        raise DomainError(403, "profile_blocked", "Profil jest zablokowany.")
    fingerprint = token_hash(f"{declaration}:{term_version}:{acknowledge_late}")
    receipt = await db.get(EnrollmentMutation, (player.id, meeting.id, key))
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise DomainError(
                409,
                "idempotency_conflict",
                "Ten identyfikator żądania został już użyty do innej operacji.",
            )
        return meeting
    check_open(meeting, term_version, at)
    entry = await db.scalar(
        select(Enrollment).where(
            Enrollment.meeting_id == meeting.id, Enrollment.player_id == player.id
        )
    )
    db.add(
        EnrollmentMutation(
            player_id=player.id,
            meeting_id=meeting.id,
            key=key,
            fingerprint=fingerprint,
            created_at=at,
        )
    )
    if entry and entry.declaration == declaration:
        if declaration == "going" and entry.reconfirmation_required:
            entry.reconfirmation_required = False
            if entry.reservation_kind == "reconfirmation":
                entry.allocation, entry.reservation_kind = "seat", None
                entry.confirmed_term_version = meeting.term_version
            elif entry.allocation == "waitlist":
                await rebalance(db, meeting, player.id, at)
            event(
                db,
                meeting,
                player.id,
                player.id,
                "term_reconfirmed",
                at,
                term_version=meeting.term_version,
            )
            meeting.version += 1
        return meeting
    kind = cancellation_kind(meeting, entry, at)
    if declaration != "going" and kind == "late" and not acknowledge_late:
        raise DomainError(
            409,
            "late_acknowledgement_required",
            "To będzie późna rezygnacja. Potwierdź ją po odświeżeniu informacji.",
        )
    newcomer = declaration == "going" and (not entry or entry.declaration != "going")
    if entry is None:
        entry = Enrollment(
            meeting_id=meeting.id,
            player_id=player.id,
            declaration=declaration,
            allocation="none",
            declared_at=at,
        )
        db.add(entry)
    else:
        await revoke_offer(db, meeting, entry, player.id, at)
        entry.declaration = declaration
        entry.reconfirmation_required = False
        entry.allocation, entry.reservation_kind = "none", None
        entry.confirmed_term_version = None
        entry.accepted_late_offer = False
        if newcomer:
            entry.declared_at = at
            entry.queue_number = await db.scalar(
                text("SELECT nextval(pg_get_serial_sequence('enrollments','queue_number'))")
            )
    await db.flush()
    event(
        db,
        meeting,
        player.id,
        player.id,
        "declared" if declaration == "going" else "withdrawn",
        at,
        declaration=declaration,
        cancellation_kind=kind if declaration != "going" else "none",
        queue_number=entry.queue_number,
    )
    await rebalance(
        db,
        meeting,
        player.id,
        at,
        newcomer_id=player.id if newcomer else None,
        allow_displace=newcomer,
    )
    meeting.version += 1
    return meeting


async def propose(db, meeting_id, player_id, term_version, actor, at):
    meeting = await lock_meeting(db, meeting_id)
    at = current_time(at)
    check_open(meeting, term_version, at)
    offer = await active_offer(db, meeting.id, player_id)
    if not offer or offer.term_version != term_version:
        raise DomainError(409, "no_reservation", "Ta osoba nie ma aktualnej rezerwacji miejsca.")
    if offer.state == "reserved":
        offer.state, offer.proposed_at, offer.created_by = "pending", at, actor.id
        event(db, meeting, player_id, actor.id, "offer_proposed", at, offer_id=str(offer.id))
        meeting.version += 1
    return offer


async def respond(db, offer_id, actor, term_version, at, action):
    # Read only the parent ID before locking. All state is refreshed after the Meeting lock.
    parent = await db.scalar(select(SeatOffer.meeting_id).where(SeatOffer.id == offer_id))
    if parent is None:
        raise DomainError(404, "not_found", "Nie znaleziono propozycji miejsca.")
    meeting = await lock_meeting(db, parent)
    at = current_time(at)
    offer = await db.scalar(
        select(SeatOffer).where(SeatOffer.id == offer_id).execution_options(populate_existing=True)
    )
    if action != "close" and offer.player_id != actor.id:
        raise DomainError(403, "forbidden", "Ta propozycja jest przeznaczona dla innej osoby.")
    check_open(meeting, term_version, at)
    if offer.term_version != meeting.term_version:
        raise DomainError(409, "stale_offer", "Propozycja dotyczy nieaktualnego terminu.")
    entry = await db.scalar(
        select(Enrollment).where(
            Enrollment.meeting_id == meeting.id, Enrollment.player_id == offer.player_id
        )
    )
    target = await db.get(Player, offer.player_id)
    terminal = {"accept": "accepted", "decline": "declined", "close": "closed"}[action]
    if not entry or not target.is_active or entry.queue_number != offer.enrollment_sequence:
        raise DomainError(409, "stale_offer", "Ta propozycja nie jest już aktualna.")
    if offer.state == terminal:
        if action == "accept" and (
            entry.allocation != "seat" or entry.confirmed_term_version != meeting.term_version
        ):
            raise DomainError(409, "stale_offer", "Ta propozycja nie jest już aktualna.")
        return meeting
    allowed = ACTIVE_OFFERS if action == "close" else ("pending",)
    if (
        offer.state not in allowed
        or entry.declaration != "going"
        or entry.allocation != "reserved"
        or entry.reservation_kind != "offer"
    ):
        raise DomainError(409, "stale_offer", "Ta propozycja nie jest już aktualna.")
    offer.state, offer.responded_at = terminal, at
    entry.reconfirmation_required = False
    if action == "accept":
        entry.allocation, entry.reservation_kind = "seat", None
        entry.confirmed_term_version = meeting.term_version
        entry.accepted_late_offer = at >= meeting.starts_at - timedelta(hours=24)
    else:
        entry.declaration, entry.allocation, entry.reservation_kind = "withdrawn", "none", None
        entry.confirmed_term_version, entry.accepted_late_offer = None, False
    event(
        db,
        meeting,
        entry.player_id,
        actor.id,
        f"offer_{terminal}",
        at,
        offer_id=str(offer.id),
        accepted_late_offer=entry.accepted_late_offer,
    )
    await db.flush()  # Close the unique active offer before reserving the next person's seat.
    await rebalance(db, meeting, actor.id, at)
    meeting.version += 1
    return meeting


async def update_player_allocations(db, player, actor_id, at, blocking, priority_changed):
    # Caller holds the identity advisory lock; all enrollment mutations acquire it first.
    time_source = at
    at = current_time(time_source)
    affected = (
        await db.scalars(
            select(Meeting)
            .join(Enrollment, Enrollment.meeting_id == Meeting.id)
            .where(
                Enrollment.player_id == player.id,
                Enrollment.declaration == "going",
                Meeting.starts_at > at,
                Meeting.status.notin_(["cancelled", "completed"]),
            )
            .order_by(Meeting.id)
        )
    ).all()
    for candidate in affected:
        meeting = await lock_meeting(db, candidate.id)
        at = current_time(time_source)
        if meeting.starts_at <= at or meeting.status in {"cancelled", "completed"}:
            continue
        entry = await db.scalar(
            select(Enrollment).where(
                Enrollment.meeting_id == meeting.id, Enrollment.player_id == player.id
            )
        )
        if blocking:
            await revoke_offer(db, meeting, entry, actor_id, at)
            entry.declaration, entry.allocation, entry.reservation_kind = "withdrawn", "none", None
            entry.confirmed_term_version, entry.accepted_late_offer = None, False
            entry.reconfirmation_required = False
            event(db, meeting, player.id, actor_id, "profile_blocked", at)
            await db.flush()
        elif priority_changed:
            event(db, meeting, player.id, actor_id, "priority_changed", at)
        await rebalance(db, meeting, actor_id, at, allow_displace=priority_changed and not blocking)
        meeting.version += 1
