from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select

from app.api.errors import DomainError
from app.api.settlement_schemas import ChargeView, PlayerSettlements, ReportView, Share
from app.models.auth import Player
from app.models.meetings import Meeting
from app.models.room import Attendance
from app.models.settlements import ChargeRevision, MeetingCharge, PaymentAllocation, PaymentReport


def split_cost(cost, player_ids):
    ordered = sorted(set(player_ids))
    if not ordered:
        return {}
    base, remainder = divmod(cost, len(ordered))
    return {player_id: base + (index < remainder) for index, player_id in enumerate(ordered)}


async def meeting_charges(db, meeting_id):
    rows = await db.scalars(select(MeetingCharge).where(MeetingCharge.meeting_id == meeting_id))
    return {row.player_id: row for row in rows}


async def present_players(db, meeting_id):
    await db.flush()
    return list(
        await db.scalars(
            select(Attendance.player_id).where(
                Attendance.meeting_id == meeting_id, Attendance.confirmed_state == "present"
            )
        )
    )


def compare_shares(cost, present, previous):
    amounts = split_cost(cost, present)
    return [
        Share(
            player_id=person,
            amount=amounts.get(person, 0),
            delta=amounts.get(person, 0) - (previous[person].amount if person in previous else 0),
        )
        for person in sorted(amounts.keys() | previous.keys())
    ]


async def lock_players(db, ids):
    # Use a separate lock namespace from profile and enrollment operations.
    for identifier in sorted(set(ids)):
        await db.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"settlements:{identifier}", 0))
            )
        )


async def post_charges(db, meeting, actor_id, at, reason):
    old = await meeting_charges(db, meeting.id)
    present = await present_players(db, meeting.id)
    changes = [share for share in compare_shares(meeting.cost_grosz, present, old) if share.delta]
    if not changes:
        return
    await lock_players(db, [share.player_id for share in changes])
    for share in changes:
        row = old.get(share.player_id)
        if row is None:
            row = MeetingCharge(meeting_id=meeting.id, player_id=share.player_id, posted_at=at)
            db.add(row)
        elif row.amount == 0:
            row.posted_at = at
        row.amount = share.amount
        db.add(
            ChargeRevision(
                meeting_id=meeting.id,
                player_id=share.player_id,
                delta=share.delta,
                reason=reason,
                actor_id=actor_id,
                created_at=at,
            )
        )


async def recipient(db):
    return await db.scalar(
        select(Player).where(Player.role == "admin").order_by(Player.created_at, Player.id).limit(1)
    )


def name(player):
    return f"{player.first_name} {player.last_name}"


async def views(db, players, now):
    ids = [player.id for player in players]
    charges = (
        await db.execute(
            select(MeetingCharge, Meeting.starts_at)
            .join(Meeting, Meeting.id == MeetingCharge.meeting_id)
            .where(MeetingCharge.player_id.in_(ids))
            .order_by(MeetingCharge.posted_at, MeetingCharge.meeting_id)
        )
    ).all()
    allocations = (
        await db.execute(
            select(PaymentReport, PaymentAllocation)
            .join(PaymentAllocation, PaymentAllocation.report_id == PaymentReport.id)
            .where(PaymentReport.player_id.in_(ids))
            .order_by(
                PaymentReport.created_at.desc(), PaymentReport.id, PaymentAllocation.meeting_id
            )
        )
    ).all()
    paid, pending = defaultdict(int), defaultdict(int)
    reports = defaultdict(dict)
    for report, allocation in allocations:
        key = report.player_id, allocation.meeting_id
        if report.status == "paid":
            paid[key] += allocation.amount
        elif report.status == "pending":
            pending[key] += allocation.amount
        report_view = reports[report.player_id].get(report.id)
        if report_view is None:
            report_view = ReportView(
                id=report.id,
                status=report.status,
                amount=0,
                meeting_ids=[],
                created_at=report.created_at,
                reviewed_at=report.reviewed_at,
                reason=report.reason,
            )
            reports[report.player_id][report.id] = report_view
        report_view.amount += allocation.amount
        report_view.meeting_ids.append(allocation.meeting_id)
    player_charges = defaultdict(list)
    for charge, starts_at in charges:
        key = charge.player_id, charge.meeting_id
        player_charges[charge.player_id].append(
            ChargeView(
                meeting_id=charge.meeting_id,
                starts_at=starts_at,
                posted_at=charge.posted_at,
                amount=charge.amount,
                due=max(0, charge.amount - paid[key] - pending[key]),
                pending=pending[key],
                paid=paid[key],
            )
        )
    result = []
    for player in players:
        rows = player_charges[player.id]
        credit = sum(max(0, row.paid - row.amount) for row in rows)
        for row in rows:
            offset = min(row.due, credit)
            credit -= offset
            row.due -= offset
        oldest = next((row.posted_at for row in rows if row.due), None)
        due = sum(row.due for row in rows)
        result.append(
            PlayerSettlements(
                player_id=player.id,
                name=name(player),
                due=due,
                credit=credit,
                pending=sum(row.pending for row in rows),
                oldest_due_at=oldest,
                reminder=due > 10_000 or (oldest is not None and now - oldest > timedelta(days=30)),
                charges=rows,
                reports=list(reports[player.id].values()),
            )
        )
    return result


async def report_payment(db, player, body, at, reviewer=None):
    await lock_players(db, [player.id])
    existing = await db.get(PaymentReport, body.id)
    if existing is not None:
        if existing.player_id == player.id:
            rows = list(
                await db.scalars(
                    select(PaymentAllocation).where(PaymentAllocation.report_id == body.id)
                )
            )
            if {row.meeting_id for row in rows} == set(body.meeting_ids) and sum(
                row.amount for row in rows
            ) == body.amount:
                return
        raise DomainError(409, "payment_conflict", "To zgłoszenie zostało już zapisane.")
    target = await recipient(db)
    if target is None:
        raise DomainError(409, "no_recipient", "Brak odbiorcy wpłat.")
    view = (await views(db, [player], at))[0]
    available = {charge.meeting_id: charge.due for charge in view.charges}
    selected = {identifier: available.get(identifier, 0) for identifier in body.meeting_ids}
    if not all(selected.values()) or sum(selected.values()) != body.amount:
        raise DomainError(
            409, "payment_conflict", "Saldo się zmieniło. Wczytaj aktualne rozliczenia."
        )
    db.add(
        PaymentReport(
            id=body.id,
            player_id=player.id,
            recipient_id=target.id,
            status="paid" if reviewer else "pending",
            created_at=at,
            reviewed_at=at if reviewer else None,
            reviewer_id=reviewer.id if reviewer else None,
        )
    )
    await db.flush()
    db.add_all(
        PaymentAllocation(report_id=body.id, meeting_id=key, amount=amount)
        for key, amount in selected.items()
    )


async def review_payment(db, report_id, body, actor, at):
    player_id = await db.scalar(
        select(PaymentReport.player_id).where(PaymentReport.id == report_id)
    )
    if player_id is None:
        raise DomainError(404, "not_found", "Nie znaleziono zgłoszenia wpłaty.")
    await lock_players(db, [player_id])
    report = await db.get(PaymentReport, report_id)
    if report.status == body.status:
        return
    if report.status != "pending":
        raise DomainError(409, "payment_conflict", "Wpłata została już sprawdzona.")
    report.status = body.status
    report.reason = body.reason
    report.reviewed_at = at
    report.reviewer_id = actor.id
