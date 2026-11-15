from fastapi import APIRouter, Depends, Request, Response

from app.api.auth import DB, User, guard
from app.api.auth_schemas import (
    Done,
    GoogleConfig,
    GoogleConnection,
    GoogleRedirect,
    GoogleStart,
    PinInput,
)
from app.api.errors import ApiError
from app.models.auth import GoogleIdentity
from app.services import google_auth as service

router = APIRouter(
    tags=["google-auth"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (400, 401, 403, 409, 422, 429, 503)},
)


@router.get("/auth/google/config", response_model=GoogleConfig, operation_id="getGoogleConfig")
async def config(request: Request) -> GoogleConfig:
    settings = request.app.state.settings
    return GoogleConfig(enabled=settings.google_enabled, public_url=settings.public_url)


@router.get("/me/google", response_model=GoogleConnection, operation_id="getGoogleConnection")
async def connection(player: User, db: DB) -> GoogleConnection:
    return GoogleConnection(connected=await db.get(GoogleIdentity, player.id) is not None)


@router.post("/auth/google/start", response_model=GoogleRedirect, operation_id="startGoogleAuth")
async def start(body: GoogleStart, request: Request, response: Response, db: DB) -> GoogleRedirect:
    url = await service.start_flow(
        db,
        request,
        response,
        body.mode,
        body.pin.get_secret_value() if body.pin is not None else None,
        body.return_to,
    )
    return GoogleRedirect(url=url)


@router.get("/auth/google/callback", operation_id="finishGoogleAuth", include_in_schema=False)
async def callback(request: Request, db: DB):
    return await service.finish_flow(request, db)


@router.post("/me/google/disconnect", response_model=Done, operation_id="disconnectGoogle")
async def disconnect(
    body: PinInput, player: User, request: Request, response: Response, db: DB
) -> Done:
    await service.disconnect_identity(db, player, body.pin.get_secret_value(), request, response)
    return Done()
