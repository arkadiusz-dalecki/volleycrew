from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime
from sqlalchemy import func, select

from app.api.auth import DB, User, guard
from app.api.errors import ApiError, DomainError
from app.api.meeting_schemas import (
    AdjacentMeetings,
    CalendarPage,
    MeetingDetail,
    PlayerPage,
    PublicPlayer,
    ResolveOccurrence,
    ScheduleView,
)
from app.models.auth import Player
from app.models.meetings import Meeting, ScheduleVersion
from app.services import meetings as service

router = APIRouter(
    tags=["meetings"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=10000)]


@router.get("/schedule", response_model=list[ScheduleView], operation_id="getSchedule")
async def schedule(_player: User, db: DB):
    return (
        await db.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.superseded.is_(False))
            .order_by(ScheduleVersion.effective_from)
        )
    ).all()


@router.get("/calendar", response_model=CalendarPage, operation_id="getCalendar")
async def calendar(
    _player: User,
    db: DB,
    request: Request,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    limit: Limit = 50,
    offset: Offset = 0,
):
    if not 1 <= (to_date - from_date).days <= 366 or from_date.year < 1970 or to_date.year > 9998:
        raise DomainError(422, "invalid_range", "Wybierz zakres od 1 do 366 dni, od roku 1970.")
    items = await service.calendar(db, from_date, to_date, request.app.state.clock.now())
    page = items[offset : offset + limit]
    await service.rosters(db, page)
    return CalendarPage(
        from_date=from_date,
        to_date=to_date,
        items=page,
        total=len(items),
        next_offset=offset + limit if offset + limit < len(items) else None,
    )


@router.get("/meetings/next", response_model=MeetingDetail | None, operation_id="getNextMeeting")
async def next_meeting(_player: User, db: DB, request: Request):
    item = await service.next_meeting(db, request.app.state.clock.now())
    if item is None:
        return None
    if item.persisted:
        return await service.detail(db, await db.get(Meeting, item.id))
    return MeetingDetail(**item.model_dump(), participants=[], waitlist=[])


@router.post("/meetings/resolve", response_model=MeetingDetail, operation_id="resolveMeeting")
async def resolve(body: ResolveOccurrence, _player: User, db: DB, request: Request):
    row = await service.resolve(
        db, body.schedule_version_id, body.source_date, request.app.state.clock.now()
    )
    await db.commit()
    return await service.detail(db, row)


@router.get(
    "/meetings/adjacent", response_model=AdjacentMeetings, operation_id="getAdjacentMeetings"
)
async def adjacent(
    starts_at: AwareDatetime, meeting_id: UUID, _player: User, db: DB, request: Request
):
    if not 1970 <= starts_at.year <= 9997:
        raise DomainError(422, "invalid_range", "Wybierz termin od roku 1970 do 9997.")
    return await service.adjacent(db, starts_at, meeting_id, request.app.state.clock.now())


@router.get("/meetings/{meeting_id}", response_model=MeetingDetail, operation_id="getMeeting")
async def meeting(meeting_id: UUID, _player: User, db: DB):
    row = await db.get(Meeting, meeting_id)
    if row is None:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")
    return await service.detail(db, row)


@router.get("/players", response_model=PlayerPage, operation_id="getGroupPlayers")
async def players(_player: User, db: DB, limit: Limit = 50, offset: Offset = 0):
    total = await db.scalar(
        select(func.count()).select_from(Player).where(Player.is_active.is_(True))
    )
    rows = (
        await db.scalars(
            select(Player)
            .where(Player.is_active.is_(True))
            .order_by(Player.first_name, Player.last_name, Player.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return PlayerPage(
        items=[PublicPlayer.model_validate(row) for row in rows],
        total=total,
        next_offset=offset + limit if offset + limit < total else None,
    )
