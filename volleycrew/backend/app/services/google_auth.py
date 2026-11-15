"""Browser-bound Google flows, identity linking and session lifecycle."""

from datetime import timedelta

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError
from app.core.security import SESSION_COOKIE, cookie_name, new_token, source_address, token_hash
from app.models.auth import GoogleFlow, GoogleIdentity, Player, Session
from app.services import auth
from app.services.google_provider import GoogleRejected, GoogleUnavailable

FLOW_COOKIE = "__Host-vc_google_flow"
FLOW_PATH = "/"
FLOW_TTL = timedelta(minutes=10)


def flow_cookie(request: Request) -> str:
    return FLOW_COOKIE if request.app.state.settings.cookie_secure else "vc_google_flow_dev"


def enabled(request: Request) -> None:
    if not request.app.state.settings.google_enabled:
        raise DomainError(503, "google_disabled", "Logowanie Google nie jest skonfigurowane.")
    if request.scope.get("root_path"):
        raise DomainError(
            409, "google_public_url", "Otwórz główny adres Volleycrew, aby użyć Google."
        )


async def start_flow(
    db: AsyncSession,
    request: Request,
    response: Response,
    mode: str,
    password: str | None,
    return_to: str,
) -> str:
    enabled(request)
    await auth.rate_action(db, request, "google_start", limit=60)
    session_id = None
    if mode == "link":
        player, session = await auth.current_session(db, request)
        if password is None:
            raise DomainError(422, "password_required", "Potwierdź swoje obecne hasło.")
        await auth.credential(db, request, player, player.id, password)
        if await db.get(GoogleIdentity, player.id):
            raise DomainError(409, "google_connected", "Profil ma już połączone konto Google.")
        session_id = session.id
    at = auth.now(request)
    state, browser, nonce = new_token(), new_token(), new_token()
    await db.execute(delete(GoogleFlow).where(GoogleFlow.expires_at <= at))
    # Starting a new flow in this browser invalidates its previous pending flow.
    old_browser = request.cookies.get(flow_cookie(request))
    if old_browser:
        await db.execute(
            delete(GoogleFlow).where(GoogleFlow.browser_hash == token_hash(old_browser))
        )
    db.add(
        GoogleFlow(
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
        flow_cookie(request),
        browser,
        max_age=int(FLOW_TTL.total_seconds()),
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path=FLOW_PATH,
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
        response.delete_cookie(
            flow_cookie(request),
            path=FLOW_PATH,
            httponly=True,
            samesite="lax",
            secure=request.app.state.settings.cookie_secure,
        )
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
    state, browser = params.get("state", ""), request.cookies.get(flow_cookie(request), "")
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
    grant.used_at = at
    await db.commit()  # Consume once and release the global auth lock before any Google I/O.
    if params.get("error"):
        return result(request, "cancelled", clear=True, linked=bool(session_id))
    code = params.get("code", "")
    if not code or len(code) > 4096 or len(params.getlist("code")) != 1:
        return result(request, "invalid", clear=True, linked=bool(session_id))
    try:
        subject = await request.app.state.google_provider.exchange(code, state, nonce_hash)
    except GoogleUnavailable:
        return result(request, "unavailable", clear=True, linked=bool(session_id))
    except GoogleRejected:
        return result(request, "invalid", clear=True, linked=bool(session_id))
    await auth.auth_lock(db)
    at = auth.now(request)
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
                    Player.password_hash.is_not(None),
                    Session.token_hash
                    == token_hash(request.cookies.get(cookie_name(request, SESSION_COOKIE), "")),
                )
            )
        ).first()
        if not pair:
            return result(request, "session", clear=True)
        player = pair.Player
        existing = await db.scalar(select(GoogleIdentity).where(GoogleIdentity.subject == subject))
        if existing or await db.get(GoogleIdentity, player.id):
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
                Player.password_hash.is_not(None),
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
