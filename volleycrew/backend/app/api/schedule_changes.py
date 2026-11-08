from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.auth import DB, Admin, guard
from app.api.errors import ApiError
from app.api.meeting_schemas import MeetingDetail
from app.api.schedule_schemas import (
    ApplySchedule,
    CreateMeetingInput,
    MeetingVersionInput,
    ReleaseReservation,
    RescheduleInput,
    ScheduleInput,
    SchedulePreview,
    ScheduleSettings,
)
from app.services import meetings
from app.services import schedule_changes as service

router = APIRouter(
    tags=["schedule-changes"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)


@router.get("/admin/schedule", response_model=ScheduleSettings, operation_id="getScheduleSettings")
async def settings(_actor: Admin, db: DB):
    return await service.settings(db)


@router.post(
    "/admin/schedule/preview", response_model=SchedulePreview, operation_id="previewSchedule"
)
async def preview(body: ScheduleInput, _actor: Admin, db: DB, request: Request):
    return (await service.preview(db, body, request.app.state.clock))[0]


@router.post(
    "/admin/schedule/versions", response_model=ScheduleSettings, operation_id="changeSchedule"
)
async def apply(body: ApplySchedule, actor: Admin, db: DB, request: Request):
    view = await service.apply(db, body, actor.id, request.app.state.clock)
    await db.commit()
    return view


@router.post(
    "/admin/meetings/{meeting_id}/reschedule",
    response_model=MeetingDetail,
    operation_id="rescheduleMeeting",
)
async def reschedule(
    meeting_id: UUID, body: RescheduleInput, actor: Admin, db: DB, request: Request
):
    row = await service.reschedule(db, meeting_id, body, actor.id, request.app.state.clock)
    await db.flush()
    view = await meetings.detail(db, row)
    await db.commit()
    return view


@router.post(
    "/admin/meetings/{meeting_id}/cancel",
    response_model=MeetingDetail,
    operation_id="cancelMeeting",
)
async def cancel(
    meeting_id: UUID, body: MeetingVersionInput, actor: Admin, db: DB, request: Request
):
    row = await service.cancel(db, meeting_id, body, actor.id, request.app.state.clock)
    await db.flush()
    view = await meetings.detail(db, row)
    await db.commit()
    return view


@router.post(
    "/admin/meetings/{meeting_id}/release-reconfirmation",
    response_model=MeetingDetail,
    operation_id="releaseReconfirmation",
)
async def release(
    meeting_id: UUID, body: ReleaseReservation, actor: Admin, db: DB, request: Request
):
    row = await service.release(db, meeting_id, body, actor.id, request.app.state.clock)
    await db.flush()
    view = await meetings.detail(db, row)
    await db.commit()
    return view


@router.post("/admin/meetings", response_model=MeetingDetail, operation_id="createMeeting")
async def create_meeting(body: CreateMeetingInput, actor: Admin, db: DB, request: Request):
    row = await service.create_meeting(db, body, actor.id, request.app.state.clock)
    view = await meetings.detail(db, row)
    await db.commit()
    return view
