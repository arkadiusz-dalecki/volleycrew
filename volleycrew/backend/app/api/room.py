from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.auth import DB, Admin, User, guard
from app.api.errors import ApiError, DomainError
from app.api.room_schemas import (
    AdmitPlayer,
    AttendanceDraft,
    AttendanceView,
    CorrectionInput,
    GenerateTeams,
    HistoryPage,
    ReasonInput,
    TeamsDraft,
    TeamsView,
    VersionInput,
)
from app.models.auth import Player
from app.models.meetings import Meeting
from app.services import room

router = APIRouter(
    tags=["room"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)
RetryKey = Annotated[UUID, Header(alias="Idempotency-Key")]
Limit = Annotated[int, Query(ge=1, le=50)]
Offset = Annotated[int, Query(ge=0)]


async def meeting_or_404(db, identifier):
    meeting = await db.get(Meeting, identifier)
    if meeting is None:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    return meeting


@router.get(
    "/admin/meetings/{meeting_id}/attendance",
    response_model=AttendanceView,
    operation_id="getAttendance",
)
async def attendance(meeting_id: UUID, _actor: Admin, db: DB, request: Request):
    return await room.attendance_view(
        db, await meeting_or_404(db, meeting_id), request.app.state.clock.now()
    )


async def change(db, meeting_id, actor, body, key, request, action, team=False):
    meeting, at, replayed = await room.begin(
        db, meeting_id, actor.id, action, body, key, request.app.state.clock
    )
    if not replayed:
        if action == "save_attendance":
            await room.save_attendance(db, meeting, body)
        elif action == "confirm_attendance":
            await room.confirm_attendance(db, meeting, actor.id, at)
        elif action == "admit":
            await room.admit(db, meeting, body.player_id, actor.id, at)
        elif action == "release_reservation":
            await room.release_reservation(db, meeting, body.player_id, actor.id, at)
        elif action == "correct":
            await room.correct(db, meeting, body, actor.id, at)
        elif action == "generate":
            await room.generate(db, meeting, body.mode, actor.id, at)
        elif action == "edit_teams":
            await room.edit_teams(db, meeting, body)
        elif action == "confirm_teams":
            await room.confirm_teams(db, meeting, actor.id, at)
        elif action == "reopen":
            await room.reopen(db, meeting, actor.id, at, body.reason)
    await db.flush()
    view = (
        await room.teams_view(db, meeting, private=True)
        if team
        else await room.attendance_view(db, meeting, at)
    )
    await db.commit()
    return view


@router.put(
    "/admin/meetings/{meeting_id}/attendance",
    response_model=AttendanceView,
    operation_id="saveAttendance",
)
async def save(
    meeting_id: UUID, body: AttendanceDraft, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "save_attendance")


@router.post(
    "/admin/meetings/{meeting_id}/attendance/confirm",
    response_model=AttendanceView,
    operation_id="confirmAttendance",
)
async def confirm(
    meeting_id: UUID, body: VersionInput, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "confirm_attendance")


@router.post(
    "/admin/meetings/{meeting_id}/attendance/admit",
    response_model=AttendanceView,
    operation_id="admitPlayer",
)
async def admit(
    meeting_id: UUID, body: AdmitPlayer, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "admit")


@router.post(
    "/admin/meetings/{meeting_id}/attendance/release-reservation",
    response_model=AttendanceView,
    operation_id="releaseRoomReservation",
)
async def release(
    meeting_id: UUID, body: AdmitPlayer, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "release_reservation")


@router.post(
    "/admin/meetings/{meeting_id}/attendance/corrections",
    response_model=AttendanceView,
    operation_id="correctAttendance",
)
async def correct(
    meeting_id: UUID, body: CorrectionInput, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "correct")


@router.get(
    "/me/attendance-history", response_model=HistoryPage, operation_id="getMyAttendanceHistory"
)
async def my_history(player: User, db: DB, limit: Limit = 20, offset: Offset = 0):
    return await room.history(db, player.id, limit, offset)


@router.get(
    "/admin/players/{player_id}/attendance-history",
    response_model=HistoryPage,
    operation_id="getPlayerAttendanceHistory",
)
async def player_history(
    player_id: UUID, _actor: Admin, db: DB, limit: Limit = 20, offset: Offset = 0
):
    if await db.get(Player, player_id) is None:
        raise DomainError(404, "not_found", "Nie znaleziono profilu.")
    return await room.history(db, player_id, limit, offset)


@router.get(
    "/meetings/{meeting_id}/teams",
    response_model=TeamsView | None,
    operation_id="getConfirmedTeams",
)
async def public_teams(meeting_id: UUID, _player: User, db: DB):
    return await room.teams_view(db, await meeting_or_404(db, meeting_id))


@router.get(
    "/admin/meetings/{meeting_id}/teams",
    response_model=TeamsView | None,
    operation_id="getTeamDraft",
)
async def private_teams(meeting_id: UUID, _actor: Admin, db: DB):
    return await room.teams_view(db, await meeting_or_404(db, meeting_id), private=True)


@router.post(
    "/admin/meetings/{meeting_id}/teams/generate",
    response_model=TeamsView | None,
    operation_id="generateTeams",
)
async def generate(
    meeting_id: UUID, body: GenerateTeams, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "generate", team=True)


@router.put(
    "/admin/meetings/{meeting_id}/teams", response_model=TeamsView | None, operation_id="saveTeams"
)
async def edit(
    meeting_id: UUID, body: TeamsDraft, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "edit_teams", team=True)


@router.post(
    "/admin/meetings/{meeting_id}/teams/confirm",
    response_model=TeamsView | None,
    operation_id="confirmTeams",
)
async def confirm_teams(
    meeting_id: UUID, body: VersionInput, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "confirm_teams", team=True)


@router.post(
    "/admin/meetings/{meeting_id}/teams/reopen",
    response_model=TeamsView | None,
    operation_id="reopenTeams",
)
async def reopen(
    meeting_id: UUID, body: ReasonInput, actor: Admin, db: DB, key: RetryKey, request: Request
):
    return await change(db, meeting_id, actor, body, key, request, "reopen", team=True)
