from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_schemas import (
    AdminPlayerPatch,
    ChangePin,
    CsrfView,
    Done,
    InviteView,
    LinkCreated,
    Login,
    LoginProfile,
    PlayerView,
    ProfileInput,
    Registration,
    ResetPin,
)
from app.api.errors import ApiError, DomainError
from app.core.deps import get_session
from app.core.security import (
    RESET_TTL,
    SESSION_COOKIE,
    cookie_name,
    cookie_path,
    hash_pin,
    new_token,
    set_csrf,
    token_hash,
)
from app.models.auth import BootstrapGrant, Invite, PinResetGrant, Player, Session
from app.services import auth as service
from app.services.enrollment import update_player_allocations

DB = Annotated[AsyncSession, Depends(get_session)]


async def guard(request: Request, db: DB) -> None:
    await service.guard_mutation(request, db)


async def user(request: Request, db: DB) -> Player:
    return (await service.current_session(db, request))[0]


async def admin(player: Annotated[Player, Depends(user)]) -> Player:
    if player.role != "admin":
        raise DomainError(403, "forbidden", "Ta czynność jest dostępna tylko dla organizatora.")
    return player


User = Annotated[Player, Depends(user)]
Admin = Annotated[Player, Depends(admin)]
router = APIRouter(
    tags=["auth"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (400, 401, 403, 404, 409, 422, 429, 500)},
)


@router.get("/auth/csrf", response_model=CsrfView, operation_id="getCsrf")
async def csrf(request: Request, response: Response) -> CsrfView:
    return CsrfView(
        token=set_csrf(
            response,
            request,
            request.cookies.get(cookie_name(request, SESSION_COOKIE), ""),
            service.now(request),
        )
    )


@router.get("/auth/profiles", response_model=list[LoginProfile], operation_id="getLoginProfiles")
async def profiles(db: DB) -> list[LoginProfile]:
    players = (await db.scalars(select(Player).where(Player.is_active.is_(True)))).all()
    views = [
        LoginProfile(
            profile_id=p.id,
            first_name=p.first_name,
            masked_last_name=p.last_name[0] + "*****" + p.last_name[-1],
            nickname=p.nickname,
        )
        for p in players
    ]
    return sorted(
        views,
        key=lambda p: (
            p.first_name.casefold(),
            p.masked_last_name,
            p.nickname or "",
            str(p.profile_id),
        ),
    )


@router.post("/auth/bootstrap", response_model=PlayerView, operation_id="bootstrapAdmin")
async def bootstrap(body: Registration, request: Request, response: Response, db: DB) -> Player:
    await service.rate_action(db, request, "bootstrap")
    grant = await db.get(BootstrapGrant, 1)
    exists = await db.scalar(select(Player.id).where(Player.role == "admin").limit(1))
    at = service.now(request)
    if (
        exists
        or not grant
        or grant.used_at
        or grant.expires_at <= at
        or grant.token_hash != token_hash(body.token.get_secret_value())
    ):
        await service.invalid_token(db)
    player = Player(
        first_name=body.first_name,
        last_name=body.last_name,
        nickname=body.nickname,
        pin_hash=await hash_pin(body.pin.get_secret_value()),
        role="admin",
        priority_status="founder",
        created_at=at,
    )
    db.add(player)
    await db.flush()
    grant.used_at = at
    service.audit(db, player.id, "bootstrap_admin", player.id, at)
    await service.new_session(db, player, request, response)
    await db.commit()
    return player


@router.post("/auth/register", response_model=PlayerView, operation_id="registerPlayer")
async def register(body: Registration, request: Request, response: Response, db: DB) -> Player:
    await service.rate_action(db, request, "registration")
    invite = await db.scalar(
        select(Invite).where(
            Invite.token_hash == token_hash(body.token.get_secret_value()),
            Invite.revoked_at.is_(None),
        )
    )
    if not invite:
        await service.invalid_token(db)
    player = Player(
        first_name=body.first_name,
        last_name=body.last_name,
        nickname=body.nickname,
        pin_hash=await hash_pin(body.pin.get_secret_value()),
        role="player",
        priority_status="guest",
        created_at=service.now(request),
    )
    db.add(player)
    await db.flush()
    service.audit(
        db, player.id, "register", player.id, service.now(request), {"invite_id": str(invite.id)}
    )
    await service.new_session(db, player, request, response)
    await db.commit()
    return player


@router.post("/auth/login", response_model=PlayerView, operation_id="login")
async def login(body: Login, request: Request, response: Response, db: DB) -> Player:
    player = await service.credential(
        db,
        request,
        await db.get(Player, body.profile_id),
        body.profile_id,
        body.pin.get_secret_value(),
    )
    await service.new_session(db, player, request, response)
    await db.commit()
    return player


@router.post("/auth/logout", response_model=Done, operation_id="logout")
async def logout(request: Request, response: Response, db: DB) -> Done:
    await db.execute(
        update(Session)
        .where(
            Session.token_hash
            == token_hash(request.cookies.get(cookie_name(request, SESSION_COOKIE), ""))
        )
        .values(revoked_at=service.now(request))
    )
    response.delete_cookie(
        cookie_name(request, SESSION_COOKIE),
        path=cookie_path(request),
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    set_csrf(response, request, "", service.now(request))
    await db.commit()
    return Done()


@router.get("/me", response_model=PlayerView, operation_id="getMe")
async def me(player: User) -> Player:
    return player


@router.patch("/me", response_model=PlayerView, operation_id="updateMe")
async def update_me(body: ProfileInput, player: User, request: Request, db: DB) -> Player:
    player.first_name, player.last_name, player.nickname = (
        body.first_name,
        body.last_name,
        body.nickname,
    )
    service.audit(db, player.id, "update_profile", player.id, service.now(request))
    await db.commit()
    return player


@router.post("/me/pin", response_model=Done, operation_id="changePin")
async def change_pin(
    body: ChangePin, player: User, request: Request, response: Response, db: DB
) -> Done:
    await service.credential(db, request, player, player.id, body.current_pin.get_secret_value())
    player.pin_hash = await hash_pin(body.pin.get_secret_value())
    await service.revoke_sessions(db, player.id, service.now(request))
    await db.execute(
        update(PinResetGrant)
        .where(PinResetGrant.player_id == player.id, PinResetGrant.used_at.is_(None))
        .values(used_at=service.now(request))
    )
    await service.new_session(db, player, request, response)
    service.audit(db, player.id, "change_pin", player.id, service.now(request))
    await db.commit()
    return Done()


@router.post("/auth/reset-pin", response_model=PlayerView, operation_id="resetPin")
async def reset_pin(body: ResetPin, request: Request, response: Response, db: DB) -> Player:
    await service.rate_action(db, request, "reset")
    at = service.now(request)
    grant = await db.scalar(
        select(PinResetGrant).where(
            PinResetGrant.token_hash == token_hash(body.token.get_secret_value())
        )
    )
    player = await db.get(Player, grant.player_id) if grant else None
    if not grant or grant.used_at or grant.expires_at <= at or not player or not player.is_active:
        await service.invalid_token(db)
    player.pin_hash = await hash_pin(body.pin.get_secret_value())
    await db.execute(
        update(PinResetGrant)
        .where(PinResetGrant.player_id == player.id, PinResetGrant.used_at.is_(None))
        .values(used_at=at)
    )
    await service.revoke_sessions(db, player.id, at)
    await service.new_session(db, player, request, response)
    service.audit(db, player.id, "reset_pin", player.id, at)
    await db.commit()
    return player


@router.get("/admin/invites", response_model=list[InviteView], operation_id="getInvites")
async def invites(_actor: Admin, db: DB) -> list[Invite]:
    return list((await db.scalars(select(Invite).order_by(Invite.created_at.desc()))).all())


@router.post("/admin/invites", response_model=LinkCreated, operation_id="createInvite")
async def create_invite(actor: Admin, db: DB, request: Request) -> LinkCreated:
    value = new_token()
    invite = Invite(
        token_hash=token_hash(value), created_by=actor.id, created_at=service.now(request)
    )
    db.add(invite)
    await db.flush()
    service.audit(db, actor.id, "create_invite", invite.id, service.now(request))
    await db.commit()
    return LinkCreated(id=invite.id, url=f"{request.app.state.settings.public_url}/join#{value}")


@router.post("/admin/invites/{invite_id}/revoke", response_model=Done, operation_id="revokeInvite")
async def revoke_invite(invite_id: UUID, actor: Admin, db: DB, request: Request) -> Done:
    invite = await db.get(Invite, invite_id)
    if invite is None:
        raise DomainError(404, "not_found", "Nie znaleziono zaproszenia.")
    if invite.revoked_at is None:
        invite.revoked_at = service.now(request)
        service.audit(db, actor.id, "revoke_invite", invite.id, service.now(request))
    await db.commit()
    return Done()


@router.get("/admin/players", response_model=list[PlayerView], operation_id="getPlayers")
async def players(_actor: Admin, db: DB) -> list[Player]:
    return list((await db.scalars(select(Player).order_by(Player.created_at))).all())


@router.patch(
    "/admin/players/{player_id}", response_model=PlayerView, operation_id="updatePlayerAccess"
)
async def update_player_access(
    player_id: UUID, body: AdminPlayerPatch, actor: Admin, db: DB, request: Request
) -> Player:
    player = await db.get(Player, player_id)
    if player is None:
        raise DomainError(404, "not_found", "Nie znaleziono zawodnika.")
    if body.is_active is None and body.priority_status is None:
        raise DomainError(422, "validation_error", "Podaj nowy stan profilu.")
    if player.role == "admin" and body.is_active is False:
        raise DomainError(
            409, "cannot_block_admin", "Nie można zablokować jedynego administratora."
        )
    active_changed = body.is_active is not None and player.is_active != body.is_active
    priority_changed = (
        body.priority_status is not None and player.priority_status != body.priority_status
    )
    if active_changed or priority_changed:
        if active_changed:
            player.is_active = body.is_active
        if priority_changed:
            player.priority_status = body.priority_status
        if not player.is_active:
            await service.revoke_sessions(db, player.id, service.now(request))
            await db.execute(
                update(PinResetGrant)
                .where(PinResetGrant.player_id == player.id, PinResetGrant.used_at.is_(None))
                .values(used_at=service.now(request))
            )
        await update_player_allocations(
            db,
            player,
            actor.id,
            request.app.state.clock,
            blocking=active_changed and not player.is_active,
            priority_changed=priority_changed,
        )
        service.audit(
            db,
            actor.id,
            "update_player_access",
            player.id,
            service.now(request),
            {"is_active": player.is_active, "priority_status": player.priority_status},
        )
    await db.commit()
    return player


@router.post(
    "/admin/players/{player_id}/pin-reset",
    response_model=LinkCreated,
    operation_id="createPinReset",
)
async def pin_reset(player_id: UUID, actor: Admin, db: DB, request: Request) -> LinkCreated:
    player = await db.get(Player, player_id)
    if player is None or not player.is_active:
        raise DomainError(404, "not_found", "Nie znaleziono aktywnego zawodnika.")
    at, value = service.now(request), new_token()
    await db.execute(
        update(PinResetGrant)
        .where(PinResetGrant.player_id == player_id, PinResetGrant.used_at.is_(None))
        .values(used_at=at)
    )
    grant = PinResetGrant(
        player_id=player_id,
        created_by=actor.id,
        token_hash=token_hash(value),
        created_at=at,
        expires_at=at + RESET_TTL,
    )
    db.add(grant)
    await db.flush()
    service.audit(db, actor.id, "create_pin_reset", player_id, at)
    await db.commit()
    return LinkCreated(
        id=grant.id, url=f"{request.app.state.settings.public_url}/reset-pin#{value}"
    )
