from fastapi import APIRouter, Depends, Request, Response

from app.api.auth import DB, User, guard
from app.api.auth_schemas import (
    Done,
    GoogleActionToken,
    GoogleActionView,
    GoogleConfig,
    GoogleConnection,
    GooglePassword,
    GoogleRedirect,
    GoogleRegistration,
    GoogleStart,
    PasswordInput,
    PlayerView,
)
from app.api.errors import ApiError
from app.models.auth import GoogleIdentity
from app.services import google_actions as actions
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
        body.password.get_secret_value() if body.password is not None else None,
        body.return_to,
        body.invite_token.get_secret_value() if body.invite_token is not None else None,
    )
    return GoogleRedirect(url=url)


@router.get("/auth/google/callback", operation_id="finishGoogleAuth", include_in_schema=False)
async def callback(request: Request, db: DB):
    return await service.finish_flow(request, db)


@router.post("/me/google/disconnect", response_model=Done, operation_id="disconnectGoogle")
async def disconnect(
    body: PasswordInput, player: User, request: Request, response: Response, db: DB
) -> Done:
    await service.disconnect_identity(
        db, player, body.password.get_secret_value(), request, response
    )
    return Done()


@router.post(
    "/auth/google/completion", response_model=GoogleActionView, operation_id="getGoogleCompletion"
)
async def completion(body: GoogleActionToken, request: Request, db: DB) -> GoogleActionView:
    grant = await actions.peek(db, request, body.token.get_secret_value())
    return GoogleActionView(
        purpose=grant.purpose, first_name=grant.first_name, last_name=grant.last_name
    )


@router.post("/auth/google/register", response_model=PlayerView, operation_id="registerWithGoogle")
async def register_google(body: GoogleRegistration, request: Request, response: Response, db: DB):
    return await actions.register(db, request, response, body)


@router.post(
    "/me/google/password", response_model=PlayerView, operation_id="setGoogleAccountPassword"
)
async def set_google_password(
    body: GooglePassword, player: User, request: Request, response: Response, db: DB
):
    return await actions.set_password(db, request, response, body, player)
