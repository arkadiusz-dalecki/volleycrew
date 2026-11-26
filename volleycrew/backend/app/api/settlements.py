from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.api.auth import DB, Admin, User, guard
from app.api.errors import ApiError, DomainError
from app.api.room import RetryKey
from app.api.settlement_schemas import (
    CorrectCost,
    CostPreview,
    MySettlements,
    PaymentDetails,
    PlayerSettlements,
    Recipient,
    ReportPayment,
    ReviewPayment,
)
from app.models.auth import Player
from app.services import enrollment, room, settlements

router = APIRouter(
    tags=["settlements"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)


@router.get("/me/payment-details", response_model=PaymentDetails, operation_id="getPaymentDetails")
async def payment_details(actor: Admin):
    return PaymentDetails(blik_phone=actor.blik_phone, revolut_link=actor.revolut_link)


@router.put("/me/payment-details", response_model=PaymentDetails, operation_id="savePaymentDetails")
async def save_details(body: PaymentDetails, actor: Admin, db: DB):
    actor.blik_phone, actor.revolut_link = body.blik_phone, body.revolut_link
    await db.commit()
    return body


@router.get("/me/settlements", response_model=MySettlements, operation_id="getMySettlements")
async def my_settlements(actor: User, db: DB, request: Request):
    view = (await settlements.views(db, [actor], request.app.state.clock.now()))[0]
    recipient = await settlements.recipient(db) if view.due else None
    return MySettlements(
        **view.model_dump(),
        recipient=Recipient(
            name=settlements.name(recipient),
            blik_phone=recipient.blik_phone,
            revolut_link=recipient.revolut_link,
        )
        if recipient
        else None,
    )


@router.get(
    "/admin/settlements", response_model=list[PlayerSettlements], operation_id="getAdminSettlements"
)
async def dashboard(_actor: Admin, db: DB, request: Request):
    people = list(await db.scalars(select(Player).order_by(Player.last_name, Player.first_name)))
    return await settlements.views(db, people, request.app.state.clock.now())


@router.post("/me/settlements/payments", status_code=204, operation_id="reportPayment")
async def report(body: ReportPayment, actor: User, db: DB, request: Request):
    await settlements.report_payment(db, actor, body, request.app.state.clock.now())
    await db.commit()


@router.post(
    "/admin/settlements/payments/{report_id}", status_code=204, operation_id="reviewPayment"
)
async def review(report_id: UUID, body: ReviewPayment, actor: Admin, db: DB, request: Request):
    await settlements.review_payment(db, report_id, body, actor, request.app.state.clock.now())
    await db.commit()


@router.post(
    "/admin/settlements/players/{player_id}/payments", status_code=204, operation_id="recordPayment"
)
async def record(player_id: UUID, body: ReportPayment, actor: Admin, db: DB, request: Request):
    payer = await db.get(Player, player_id)
    if payer is None:
        raise DomainError(404, "not_found", "Nie znaleziono gracza.")
    await settlements.report_payment(db, payer, body, request.app.state.clock.now(), reviewer=actor)
    await db.commit()


async def cost_view(db, meeting, cost):
    return CostPreview(
        meeting_id=meeting.id,
        version=meeting.version,
        cost_grosz=cost,
        shares=settlements.compare_shares(
            cost,
            await settlements.present_players(db, meeting.id),
            await settlements.meeting_charges(db, meeting.id),
        ),
    )


async def locked_cost_meeting(db, meeting_id, version):
    meeting = await enrollment.lock_meeting(db, meeting_id)
    if meeting.version != version:
        raise DomainError(409, "version_conflict", "Spotkanie się zmieniło. Odśwież dane.")
    if meeting.attendance_confirmed_at is None:
        raise DomainError(409, "attendance_required", "Najpierw zatwierdź obecność.")
    return meeting


@router.post(
    "/admin/meetings/{meeting_id}/cost/preview",
    response_model=CostPreview,
    operation_id="previewCostCorrection",
)
async def preview_cost(meeting_id: UUID, body: CorrectCost, _actor: Admin, db: DB):
    meeting = await locked_cost_meeting(db, meeting_id, body.expected_version)
    return await cost_view(db, meeting, body.cost_grosz)


@router.put(
    "/admin/meetings/{meeting_id}/cost", response_model=CostPreview, operation_id="correctCost"
)
async def correct_cost(
    meeting_id: UUID, body: CorrectCost, actor: Admin, db: DB, request: Request, key: RetryKey
):
    meeting, at, replayed = await room.begin(
        db, meeting_id, actor.id, "correct_cost", body, key, request.app.state.clock
    )
    if meeting.attendance_confirmed_at is None:
        raise DomainError(409, "attendance_required", "Najpierw zatwierdź obecność.")
    if not replayed and meeting.cost_grosz != body.cost_grosz:
        meeting.cost_grosz = body.cost_grosz
        meeting.cost_overridden = True
        meeting.version += 1
        await settlements.post_charges(db, meeting, actor.id, at, body.reason)
    view = await cost_view(db, meeting, meeting.cost_grosz)
    await db.commit()
    return view
