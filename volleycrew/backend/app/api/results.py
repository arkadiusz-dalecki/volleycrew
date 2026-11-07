from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.auth import DB, Admin, User, guard
from app.api.errors import ApiError, DomainError
from app.api.result_schemas import (
    AdminResultView,
    CorrectionPreview,
    CorrectResult,
    PlayerRatingHistory,
    RankingPage,
    ResultPreview,
    ResultsPage,
    ResultView,
    SaveResult,
    ScoreInput,
)
from app.models.meetings import Meeting
from app.services import results

router = APIRouter(
    tags=["results"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)
RetryKey = Annotated[UUID, Header(alias="Idempotency-Key")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post(
    "/admin/meetings/{meeting_id}/result-preview",
    response_model=ResultPreview,
    operation_id="previewResult",
)
async def preview(meeting_id: UUID, body: ScoreInput, _actor: Admin, db: DB):
    return await results.preview(db, meeting_id, body)


@router.post(
    "/admin/meetings/{meeting_id}/result-correction-preview",
    response_model=ResultPreview,
    operation_id="previewResultCorrection",
)
async def correction_preview(meeting_id: UUID, body: CorrectionPreview, _actor: Admin, db: DB):
    return await results.preview(db, meeting_id, body, correction=True)


@router.post(
    "/admin/meetings/{meeting_id}/result", response_model=AdminResultView, operation_id="saveResult"
)
async def save(
    meeting_id: UUID, body: SaveResult, actor: Admin, db: DB, key: RetryKey, request: Request
):
    meeting = await results.save(db, meeting_id, body, actor.id, key, request.app.state.clock)
    state = await db.get(results.RatingState, 1)
    view = await results.result_view(db, meeting, state, private=True)
    await db.commit()
    return view


@router.post(
    "/admin/meetings/{meeting_id}/result/corrections",
    response_model=AdminResultView,
    operation_id="correctResult",
)
async def correct(
    meeting_id: UUID, body: CorrectResult, actor: Admin, db: DB, key: RetryKey, request: Request
):
    meeting = await results.save(
        db, meeting_id, body, actor.id, key, request.app.state.clock, correction=True
    )
    state = await db.get(results.RatingState, 1)
    view = await results.result_view(db, meeting, state, private=True)
    await db.commit()
    return view


async def view(db, meeting_id, private=False):
    state = await results.state_lock(db)
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    return await results.result_view(db, meeting, state, private=private)


@router.get(
    "/meetings/{meeting_id}/result", response_model=ResultView | None, operation_id="getResult"
)
async def public_result(meeting_id: UUID, _player: User, db: DB):
    return await view(db, meeting_id)


@router.get(
    "/admin/meetings/{meeting_id}/result",
    response_model=AdminResultView | None,
    operation_id="getAdminResult",
)
async def admin_result(meeting_id: UUID, _actor: Admin, db: DB):
    return await view(db, meeting_id, private=True)


@router.get("/ranking", response_model=RankingPage, operation_id="getRanking")
async def ranking(_player: User, db: DB, limit: Limit = 20, offset: Offset = 0):
    return await results.ranking(db, limit, offset)


@router.get("/results", response_model=ResultsPage, operation_id="getResults")
async def history(_player: User, db: DB, limit: Limit = 20, offset: Offset = 0):
    return await results.result_history(db, limit, offset)


@router.get(
    "/players/{player_id}/rating-history",
    response_model=PlayerRatingHistory,
    operation_id="getRatingHistory",
)
async def player_history(
    player_id: UUID, _player: User, db: DB, limit: Limit = 20, offset: Offset = 0
):
    return await results.player_history(db, player_id, limit, offset)
