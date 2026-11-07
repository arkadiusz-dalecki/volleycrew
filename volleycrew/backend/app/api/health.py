import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError, error_response
from app.core.database import expected_revision
from app.core.deps import get_session

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok", "ready"]


@router.get("/live", response_model=HealthStatus, operation_id="getLiveness")
async def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get(
    "/ready",
    response_model=HealthStatus,
    operation_id="getReadiness",
    responses={503: {"model": ApiError}},
)
async def ready(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthStatus | JSONResponse:
    try:
        async with asyncio.timeout(4):
            await session.execute(text("SELECT 1"))
            versions = (
                (await session.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
            if versions != [expected_revision()]:
                return error_response(503, "not_ready", "Usługa nie jest jeszcze gotowa.")
    except (SQLAlchemyError, TimeoutError, OSError):
        return error_response(503, "not_ready", "Usługa nie jest jeszcze gotowa.")
    return HealthStatus(status="ready")
