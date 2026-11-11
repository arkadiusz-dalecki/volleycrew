from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.auth import DB, Admin, User, guard
from app.api.enrollment_schemas import (
    CloseOffer,
    DeclarationInput,
    MyParticipation,
    OfferView,
    ParticipationResult,
    ProposeOffer,
    TermInput,
    WithdrawInput,
)
from app.api.errors import ApiError, DomainError
from app.models.meetings import Meeting
from app.services import enrollment, meetings, participation

router = APIRouter(
    tags=["enrollment"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)
RetryKey = Annotated[UUID, Header(alias="Idempotency-Key")]


async def result(db, meeting, player_id, at):
    await db.flush()
    return ParticipationResult(
        meeting=await meetings.detail(db, meeting),
        participation=await participation.own(db, meeting, player_id, at),
    )


@router.get(
    "/meetings/{meeting_id}/my-participation",
    response_model=MyParticipation,
    operation_id="getMyParticipation",
)
async def own(meeting_id: UUID, player: User, db: DB, request: Request):
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None or meeting.deleted_at:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    return await participation.own(db, meeting, player.id, request.app.state.clock.now())


@router.put(
    "/meetings/{meeting_id}/my-declaration",
    response_model=ParticipationResult,
    operation_id="setMyDeclaration",
)
async def declare(
    meeting_id: UUID, body: DeclarationInput, player: User, db: DB, request: Request, key: RetryKey
):
    clock = request.app.state.clock
    meeting = await enrollment.declare(
        db,
        meeting_id,
        player,
        body.declaration,
        body.term_version,
        clock,
        key,
        body.acknowledge_late,
    )
    view = await result(db, meeting, player.id, clock.now())
    await db.commit()
    return view


@router.delete(
    "/meetings/{meeting_id}/my-declaration",
    response_model=ParticipationResult,
    operation_id="withdrawMyDeclaration",
)
async def withdraw(
    meeting_id: UUID, body: WithdrawInput, player: User, db: DB, request: Request, key: RetryKey
):
    clock = request.app.state.clock
    meeting = await enrollment.declare(
        db, meeting_id, player, "withdrawn", body.term_version, clock, key, body.acknowledge_late
    )
    view = await result(db, meeting, player.id, clock.now())
    await db.commit()
    return view


@router.get(
    "/admin/meetings/{meeting_id}/offers",
    response_model=list[OfferView],
    operation_id="getSeatOffers",
)
async def offers(meeting_id: UUID, _actor: Admin, db: DB):
    return await participation.offers(db, meeting_id)


@router.post(
    "/admin/meetings/{meeting_id}/offers", response_model=OfferView, operation_id="proposeSeat"
)
async def propose(meeting_id: UUID, body: ProposeOffer, actor: Admin, db: DB, request: Request):
    offer = await enrollment.propose(
        db, meeting_id, body.player_id, body.term_version, actor, request.app.state.clock
    )
    view = await participation.offer_view(db, offer)
    await db.commit()
    return view


@router.post(
    "/offers/{offer_id}/accept", response_model=ParticipationResult, operation_id="acceptSeat"
)
async def accept(offer_id: UUID, body: TermInput, player: User, db: DB, request: Request):
    clock = request.app.state.clock
    meeting = await enrollment.respond(db, offer_id, player, body.term_version, clock, "accept")
    view = await result(db, meeting, player.id, clock.now())
    await db.commit()
    return view


@router.post(
    "/offers/{offer_id}/decline", response_model=ParticipationResult, operation_id="declineSeat"
)
async def decline(offer_id: UUID, body: TermInput, player: User, db: DB, request: Request):
    clock = request.app.state.clock
    meeting = await enrollment.respond(db, offer_id, player, body.term_version, clock, "decline")
    view = await result(db, meeting, player.id, clock.now())
    await db.commit()
    return view


@router.post(
    "/admin/offers/{offer_id}/close",
    response_model=ParticipationResult,
    operation_id="closeSeatOffer",
)
async def close(offer_id: UUID, body: CloseOffer, actor: Admin, db: DB, request: Request):
    clock = request.app.state.clock
    meeting = await enrollment.respond(db, offer_id, actor, body.term_version, clock, "close")
    view = await result(db, meeting, actor.id, clock.now())
    await db.commit()
    return view
