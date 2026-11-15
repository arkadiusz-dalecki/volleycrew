"""Browser-bound Google flows, identity linking and session lifecycle."""

from datetime import timedelta

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError
from app.core.security import (
    SESSION_COOKIE,
    clear_google_flow,
    cookie_name,
    google_flow_cookie,
    new_token,
    source_address,
    token_hash,
)
from app.models.auth import GoogleActionGrant, GoogleFlow, GoogleIdentity, Invite, Player, Session
from app.services import auth
from app.services import google_actions as actions
from app.services.google_provider import GoogleRejected, GoogleUnavailable

FLOW_TTL = timedelta(minutes=10)


async def start_flow(
    db: AsyncSession,
    request: Request,
    response: Response,
    mode: str,
    password: str | None,
    return_to: str,
    invite_token: str | None = None,
) -> str:
    actions.enabled(request)
    await auth.rate_action(db, request, "google_start", limit=60)
    session_id, invite_id = None, None
    if mode == "register":
        invite = await db.scalar(
            select(Invite).where(
                Invite.token_hash == token_hash(invite_token or ""), Invite.revoked_at.is_(None)
            )
        )
        if not invite:
            await auth.invalid_token(db)
        invite_id = invite.id
    if mode in {"link", "password"}:
        player, session = await auth.current_session(db, request)
        if mode == "link":
            if password is None:
                raise DomainError(422, "password_required", "Potwierdź swoje obecne hasło.")
            await auth.credential(db, request, player, player.id, password)
            if await db.get(GoogleIdentity, player.id):
                raise DomainError(409, "google_connected", "Profil ma już połączone konto Google.")
        elif player.has_password or not await db.get(GoogleIdentity, player.id):
            raise DomainError(
                409,
                "google_password_unavailable",
                "Ustawienie hasła wymaga konta korzystającego wyłącznie z Google.",
            )
        session_id = session.id
    at = auth.now(request)
    state, browser, nonce = new_token(), new_token(), new_token()
    await db.execute(delete(GoogleFlow).where(GoogleFlow.expires_at <= at))
    await db.execute(delete(GoogleActionGrant).where(GoogleActionGrant.expires_at <= at))
    # Starting a new flow in this browser invalidates its previous pending flow.
    old_browser = request.cookies.get(google_flow_cookie(request))
    if old_browser:
        await db.execute(
            delete(GoogleFlow).where(GoogleFlow.browser_hash == token_hash(old_browser))
        )
    if old_browser:
        await db.execute(
            delete(GoogleActionGrant).where(
                GoogleActionGrant.browser_hash == token_hash(old_browser)
            )
        )
    db.add(
        GoogleFlow(
            mode=mode,
            invite_id=invite_id,
            return_to=return_to,
            state_hash=token_hash(state),
            browser_hash=token_hash(browser),
            nonce_hash=token_hash(nonce),
            session_id=session_id,
            created_at=at,
            expires_at=at + FLOW_TTL,
        )
    )
    url = request.app.state.google_provider.authorization_url(state, nonce)
    await db.commit()
    response.set_cookie(
        google_flow_cookie(request),
        browser,
        max_age=int(FLOW_TTL.total_seconds()),
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return url


def result(
    request: Request,
    outcome: str,
    *,
    clear: bool = False,
    linked: bool = False,
    return_to: str = "/",
):
    path = "/profile" if linked else "/login"
    target = return_to if outcome == "success" else f"{path}#google={outcome}"
    response = RedirectResponse(request.app.state.settings.public_url + target, 303)
    if clear:
        clear_google_flow(response, request)
    if outcome not in {"linked", "success"}:
        request.app.state.security_monitor.record(
            "auth_google_failed", "google", source_address(request)
        )
    return response


async def finish_flow(request: Request, db: AsyncSession):
    # The provider returns a GET, protected by one-time state + browser cookie, not our POST CSRF.
    if not request.app.state.settings.google_enabled or request.scope.get("root_path"):
        return result(request, "unavailable")
    params = request.query_params
    state, browser = params.get("state", ""), request.cookies.get(google_flow_cookie(request), "")
    if len(state) != 43 or len(browser) != 43 or len(params.getlist("state")) != 1:
        return result(request, "invalid")
    await auth.auth_lock(db)
    grant = await db.get(GoogleFlow, token_hash(state))
    at = auth.now(request)
    if (
        not grant
        or grant.used_at
        or grant.expires_at <= at
        or grant.browser_hash != token_hash(browser)
    ):
        return result(request, "invalid")
    nonce_hash, session_id, return_to = grant.nonce_hash, grant.session_id, grant.return_to
    mode, invite_id, deadline, browser_hash = (
        grant.mode,
        grant.invite_id,
        grant.expires_at,
        grant.browser_hash,
    )
    grant.used_at = at
    await db.commit()  # Consume once and release the global auth lock before any Google I/O.
    if params.get("error"):
        return result(request, "cancelled", clear=True, linked=bool(session_id))
    code = params.get("code", "")
    if not code or len(code) > 4096 or len(params.getlist("code")) != 1:
        return result(request, "invalid", clear=True, linked=bool(session_id))
    try:
        profile = await request.app.state.google_provider.exchange_profile(code, state, nonce_hash)
        subject = profile.subject
    except GoogleUnavailable:
        return result(request, "unavailable", clear=True, linked=bool(session_id))
    except GoogleRejected:
        return result(request, "invalid", clear=True, linked=bool(session_id))
    await auth.auth_lock(db)
    at = auth.now(request)
    if deadline <= at:
        return result(request, "invalid", clear=True, linked=bool(session_id))
    if mode == "register":
        if not await actions.active_invite(db, invite_id):
            return result(request, "invite", clear=True)
        existing = await db.scalar(select(GoogleIdentity).where(GoogleIdentity.subject == subject))
        if existing:
            player = await db.get(Player, existing.player_id)
            if not player.is_active:
                return result(request, "unlinked", clear=True)
            response = result(request, "success", clear=True)
            await auth.new_session(db, player, request, response)
            auth.audit(db, player.id, "login_google", player.id, at)
        else:
            response = await actions.issue(
                db,
                request,
                purpose="register",
                subject=subject,
                browser_hash=browser_hash,
                expires_at=deadline,
                invite_id=invite_id,
                first_name=profile.first_name,
                last_name=profile.last_name,
            )
        await db.commit()
        return response
    if session_id:
        pair = (
            await db.execute(
                select(Player, Session)
                .join(Session, Session.player_id == Player.id)
                .where(
                    Session.id == session_id,
                    Session.revoked_at.is_(None),
                    Session.expires_at > at,
                    Session.absolute_expires_at > at,
                    Player.is_active.is_(True),
                    Session.token_hash
                    == token_hash(request.cookies.get(cookie_name(request, SESSION_COOKIE), "")),
                )
            )
        ).first()
        if not pair:
            return result(request, "session", clear=True)
        player = pair.Player
        identity = await db.get(GoogleIdentity, player.id)
        if mode == "password":
            if not identity or identity.subject != subject or player.has_password:
                return result(request, "conflict", clear=True, linked=True)
            response = await actions.issue(
                db,
                request,
                purpose="password",
                subject=subject,
                browser_hash=browser_hash,
                expires_at=deadline,
                session_id=session_id,
            )
        else:
            existing = await db.scalar(
                select(GoogleIdentity).where(GoogleIdentity.subject == subject)
            )
            if existing or identity:
                return result(request, "conflict", clear=True, linked=True)
            db.add(GoogleIdentity(player_id=player.id, subject=subject, created_at=at))
            auth.audit(db, player.id, "connect_google", player.id, at)
            response = result(request, "linked", clear=True, linked=True)
    else:
        player = await db.scalar(
            select(Player)
            .join(GoogleIdentity, GoogleIdentity.player_id == Player.id)
            .where(
                GoogleIdentity.subject == subject,
                Player.is_active.is_(True),
            )
        )
        if not player:
            return result(request, "unlinked", clear=True)
        response = result(request, "success", clear=True, return_to=return_to)
        await auth.new_session(db, player, request, response)
        auth.audit(db, player.id, "login_google", player.id, at)
    await db.commit()
    request.app.state.security_monitor.record(
        "auth_google_succeeded", "google", source_address(request)
    )
    return response


async def disconnect_identity(
    db: AsyncSession, player: Player, password: str, request: Request, response: Response
) -> None:
    if not player.has_password:
        raise DomainError(
            409,
            "last_login_method",
            "Najpierw ustaw login i hasło, aby zachować dostęp po odłączeniu Google.",
        )
    await auth.credential(db, request, player, player.id, password)
    identity = await db.get(GoogleIdentity, player.id)
    if identity:
        await db.delete(identity)
        await db.execute(
            update(GoogleFlow)
            .where(
                GoogleFlow.session_id.in_(select(Session.id).where(Session.player_id == player.id))
            )
            .values(used_at=auth.now(request))
        )
        await auth.revoke_sessions(db, player.id, auth.now(request))
        await auth.new_session(db, player, request, response)
        auth.audit(db, player.id, "disconnect_google", player.id, auth.now(request))
    await db.commit()
