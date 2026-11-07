"""Read projections keep private own-state and administrative offers separate."""

from datetime import timedelta

from sqlalchemy import select

from app.api.enrollment_schemas import MyParticipation, OfferView
from app.api.meeting_schemas import PublicPlayer
from app.models.auth import Player
from app.models.enrollment import SeatOffer
from app.services import enrollment


async def offer_view(db, offer):
    player = await db.get(Player, offer.player_id)
    return OfferView(
        id=offer.id,
        player=PublicPlayer.model_validate(player),
        term_version=offer.term_version,
        state=offer.state,
        reserved_at=offer.reserved_at,
        proposed_at=offer.proposed_at,
    )


async def own(db, meeting, player_id, at):
    pairs = await enrollment.entries(db, meeting)
    entry = next((entry for entry, _ in pairs if entry.player_id == player_id), None)
    waiting = enrollment.waiting_order(pairs)
    position = next(
        (i + 1 for i, (entry, _) in enumerate(waiting) if entry.player_id == player_id), None
    )
    offer = await enrollment.active_offer(db, meeting.id, player_id)
    return MyParticipation(
        declaration=entry.declaration if entry else None,
        needs_reconfirmation=entry.reconfirmation_required if entry else False,
        allocation=entry.allocation if entry else "none",
        position=position,
        offer=await offer_view(db, offer) if offer else None,
        can_declare=meeting.status == "scheduled" and at < meeting.starts_at,
        term_version=meeting.term_version,
        deadline=meeting.starts_at - timedelta(hours=24),
        priority_locked=at >= meeting.starts_at - timedelta(hours=24),
        cancellation_kind=enrollment.cancellation_kind(meeting, entry, at),
    )


async def offers(db, meeting_id):
    rows = (
        await db.scalars(
            select(SeatOffer)
            .where(
                SeatOffer.meeting_id == meeting_id, SeatOffer.state.in_(enrollment.ACTIVE_OFFERS)
            )
            .order_by(SeatOffer.reserved_at, SeatOffer.id)
        )
    ).all()
    return [await offer_view(db, row) for row in rows]
