"""One-time Google proofs used to confirm editable names or add local credentials."""

import unicodedata
from datetime import datetime
from uuid import UUID

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_schemas import GooglePassword, GoogleRegistration
from app.api.errors import DomainError
from app.core.security import (
    clear_google_flow,
    google_flow_cookie,
    hash_password,
    new_token,
    token_hash,
)
from app.models.auth import (
    GoogleActionGrant,
    GoogleIdentity,
    Invite,
    PasswordResetGrant,
    Player,
    Session,
)
from app.services import auth


def enabled(request: Request) -> None:
    if not request.app.state.settings.google_enabled:
        raise DomainError(503, "google_disabled", "Logowanie Google nie jest skonfigurowane.")
    if request.scope.get("root_path"):
        raise DomainError(
            409, "google_public_url", "Otwórz główny adres Volleycrew, aby użyć Google."
        )


def suggested_name(value: str) -> str:
    # Names are untrusted suggestions, never identity keys or executable content.
    return "".join(
        c
        for c in unicodedata.normalize("NFC", value)
        if not unicodedata.category(c).startswith("C")
    ).strip()[:80]


async def active_invite(db: AsyncSession, invite_id: UUID | None) -> Invite | None:
    invite = await db.get(Invite, invite_id) if invite_id else None
    return invite if invite and invite.revoked_at is None else None


async def issue(
    db: AsyncSession,
    request: Request,
    *,
    purpose: str,
    subject: str,
    browser_hash: str,
    expires_at: datetime,
    invite_id: UUID | None = None,
    session_id: UUID | None = None,
    first_name: str = "",
    last_name: str = "",
) -> RedirectResponse:
    token = new_token()
    db.add(
        GoogleActionGrant(
            token_hash=token_hash(token),
            browser_hash=browser_hash,
            purpose=purpose,
            subject=subject,
            invite_id=invite_id,
            session_id=session_id,
            first_name=suggested_name(first_name),
            last_name=suggested_name(last_name),
            created_at=auth.now(request),
            expires_at=expires_at,
        )
    )
    route = "/join/google" if purpose == "register" else "/profile/password"
    return RedirectResponse(f"{request.app.state.settings.public_url}{route}#{token}", 303)


async def pending(db: AsyncSession, request: Request, token: str) -> GoogleActionGrant:
    enabled(request)
    browser = request.cookies.get(google_flow_cookie(request), "")
    grant = await db.get(GoogleActionGrant, token_hash(token))
    if (
        len(browser) != 43
        or not grant
        or grant.used_at
        or grant.expires_at <= auth.now(request)
        or grant.browser_hash != token_hash(browser)
    ):
        await auth.invalid_token(db)
    if grant.purpose == "register":
        if not await active_invite(db, grant.invite_id):
            await auth.invalid_token(db)
    else:
        player, session = await auth.current_session(db, request)
        identity = await db.get(GoogleIdentity, player.id)
        if (
            session.id != grant.session_id
            or not identity
            or identity.subject != grant.subject
            or player.has_password
        ):
            await auth.invalid_token(db)
    return grant


async def peek(db: AsyncSession, request: Request, token: str) -> GoogleActionGrant:
    await auth.rate_action(db, request, "google_completion", limit=60)
    grant = await pending(db, request, token)
    await db.commit()
    return grant


async def register(
    db: AsyncSession, request: Request, response: Response, body: GoogleRegistration
) -> Player:
    await auth.rate_action(db, request, "registration")
    grant = await pending(db, request, body.token.get_secret_value())
    if grant.purpose != "register":
        await auth.invalid_token(db)
    at = auth.now(request)
    identity = await db.scalar(
        select(GoogleIdentity).where(GoogleIdentity.subject == grant.subject)
    )
    if identity:
        player = await db.get(Player, identity.player_id)
        if not player.is_active:
            await auth.invalid_token(db)
        # Another completion may have won. Sign into that profile, never overwrite its names.
    else:
        player = Player(
            first_name=body.first_name,
            last_name=body.last_name,
            nickname=body.nickname,
            username=None,
            password_hash=None,
            role="player",
            priority_status="guest",
            created_at=at,
        )
        db.add(player)
        await db.flush()
        db.add(GoogleIdentity(player_id=player.id, subject=grant.subject, created_at=at))
        auth.audit(
            db, player.id, "register_google", player.id, at, {"invite_id": str(grant.invite_id)}
        )
    grant.used_at = at
    grant.subject, grant.first_name, grant.last_name = "", "", ""
    await auth.new_session(db, player, request, response)
    clear_google_flow(response, request)
    await db.commit()
    return player


async def set_password(
    db: AsyncSession, request: Request, response: Response, body: GooglePassword, player: Player
) -> Player:
    grant = await pending(db, request, body.token.get_secret_value())
    if grant.purpose != "password":
        await auth.invalid_token(db)
    await auth.require_available_username(db, body.username, player.id)
    player.username, player.password_hash = (
        body.username,
        await hash_password(body.password.get_secret_value()),
    )
    at = auth.now(request)
    await db.execute(
        update(PasswordResetGrant)
        .where(PasswordResetGrant.player_id == player.id, PasswordResetGrant.used_at.is_(None))
        .values(used_at=at)
    )
    await db.execute(
        update(GoogleActionGrant)
        .where(
            GoogleActionGrant.session_id.in_(
                select(Session.id).where(Session.player_id == player.id)
            )
        )
        .values(used_at=at, subject="", first_name="", last_name="")
    )
    await auth.revoke_sessions(db, player.id, at)
    await auth.new_session(db, player, request, response)
    auth.audit(db, player.id, "set_password_google", player.id, at)
    clear_google_flow(response, request)
    await db.commit()
    return player
