from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.auth import DB, Admin, guard
from app.api.errors import ApiError
from app.api.meeting_schemas import MeetingDetail
from app.api.schedule_schemas import (
    ApplySchedule,
    ApplySeriesRemoval,
    CreateMeetingInput,
    MeetingVersionInput,
    ReleaseReservation,
    RescheduleInput,
    ScheduleInput,
    SchedulePreview,
    ScheduleSettings,
    SeriesChangePreview,
)
from app.services import meetings, series
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


@router.post("/admin/meetings/{meeting_id}/delete", status_code=204, operation_id="deleteMeeting")
async def delete_meeting(
    meeting_id: UUID, body: MeetingVersionInput, actor: Admin, db: DB, request: Request
):
    await service.delete_meeting(db, meeting_id, body, actor.id, request.app.state.clock)
    await db.commit()


@router.post(
    "/admin/schedule/rules/{rule_id}/preview",
    response_model=SeriesChangePreview,
    operation_id="previewSeriesEdit",
)
async def preview_series_edit(
    rule_id: UUID, body: ScheduleInput, _actor: Admin, db: DB, request: Request
):
    return await series.preview(db, rule_id, body, request.app.state.clock)


@router.post(
    "/admin/schedule/rules/{rule_id}/edit",
    response_model=ScheduleSettings,
    operation_id="editSeries",
)
async def edit_series(rule_id: UUID, body: ApplySchedule, actor: Admin, db: DB, request: Request):
    result = await series.apply(db, rule_id, body, actor.id, request.app.state.clock)
    await db.commit()
    return result


@router.post(
    "/admin/schedule/rules/{rule_id}/delete-preview",
    response_model=SeriesChangePreview,
    operation_id="previewSeriesDeletion",
)
async def preview_series_deletion(
    rule_id: UUID, body: MeetingVersionInput, _actor: Admin, db: DB, request: Request
):
    return await series.preview(db, rule_id, body, request.app.state.clock, remove=True)


@router.post(
    "/admin/schedule/rules/{rule_id}/delete",
    response_model=ScheduleSettings,
    operation_id="deleteSeries",
)
async def delete_series(
    rule_id: UUID, body: ApplySeriesRemoval, actor: Admin, db: DB, request: Request
):
    result = await series.apply(db, rule_id, body, actor.id, request.app.state.clock, remove=True)
    await db.commit()
    return result
