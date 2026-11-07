import math
from datetime import datetime
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError
from app.core.security import (
    ABSOLUTE,
    AUTH_LOCK,
    CSRF_COOKIE,
    DUMMY_HASH,
    HASHER,
    IDLE,
    RATE_WINDOW,
    SESSION_COOKIE,
    allowed_origins,
    cookie_name,
    cookie_path,
    hash_pin,
    new_token,
    set_csrf,
    source_address,
    token_hash,
    valid_csrf,
    verify_pin,
)
from app.models.auth import AuditEvent, AuthThrottle, Player, Session


async def auth_lock(db: AsyncSession) -> None:
    # One bounded writer at a time for this small group's identity operations.
    # E4 will combine account blocking with the meeting allocation locks.
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": AUTH_LOCK})


def now(request: Request) -> datetime:
    return request.app.state.clock.now()


def audit(
    db: AsyncSession,
    actor: UUID | None,
    action: str,
    target: UUID | None,
    at: datetime,
    details: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_id=actor, action=action, object_id=target, created_at=at, details=details or {}
        )
    )


async def guard_mutation(request: Request, db: AsyncSession) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    cookie = request.cookies.get(cookie_name(request, CSRF_COOKIE), "")
    header = request.headers.get("x-csrf-token", "")
    import hmac

    if (
        origin not in allowed_origins(request.app.state.settings)
        or not cookie
        or not hmac.compare_digest(cookie, header)
        or not valid_csrf(
            cookie,
            request.app.state.auth_key,
            request.cookies.get(cookie_name(request, SESSION_COOKIE), ""),
            now(request),
        )
    ):
        raise DomainError(403, "csrf_failed", "Odśwież stronę i spróbuj ponownie.")
    await auth_lock(db)


async def current_session(db: AsyncSession, request: Request) -> tuple[Player, Session]:
    value = request.cookies.get(cookie_name(request, SESSION_COOKIE), "")
    pair = (
        (
            await db.execute(
                select(Player, Session)
                .join(Session, Player.id == Session.player_id)
                .where(Session.token_hash == token_hash(value))
            )
        ).first()
        if value
        else None
    )
    at = now(request)
    if (
        not pair
        or not pair.Player.is_active
        or pair.Session.revoked_at is not None
        or pair.Session.expires_at <= at
        or pair.Session.absolute_expires_at <= at
    ):
        raise DomainError(401, "unauthenticated", "Zaloguj się, aby kontynuować.")
    player, session = pair
    session.last_seen_at = at
    session.expires_at = min(at + IDLE, session.absolute_expires_at)
    if request.method in {"GET", "HEAD"}:
        await db.commit()
    return player, session


async def new_session(
    db: AsyncSession, player: Player, request: Request, response: Response
) -> None:
    at, value = now(request), new_token()
    # Replace an existing session on this device, while retaining other devices.
    old = request.cookies.get(cookie_name(request, SESSION_COOKIE))
    if old:
        await db.execute(
            update(Session).where(Session.token_hash == token_hash(old)).values(revoked_at=at)
        )
    db.add(
        Session(
            player_id=player.id,
            token_hash=token_hash(value),
            created_at=at,
            last_seen_at=at,
            expires_at=at + IDLE,
            absolute_expires_at=at + ABSOLUTE,
        )
    )
    response.set_cookie(
        cookie_name(request, SESSION_COOKIE),
        value,
        max_age=int(ABSOLUTE.total_seconds()),
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path=cookie_path(request),
    )
    set_csrf(response, request, value, at)


async def revoke_sessions(
    db: AsyncSession, player_id: UUID, at: datetime, except_id: UUID | None = None
) -> None:
    query = update(Session).where(Session.player_id == player_id, Session.revoked_at.is_(None))
    if except_id:
        query = query.where(Session.id != except_id)
    await db.execute(query.values(revoked_at=at))


async def buckets(db: AsyncSession, keys: list[str], at: datetime) -> list[AuthThrottle]:
    result = []
    for raw in keys:
        key = token_hash(raw)
        bucket = await db.get(AuthThrottle, key)
        if bucket is None:
            bucket = AuthThrottle(key=key, count=0, started_at=at)
            db.add(bucket)
        elif at >= bucket.started_at + RATE_WINDOW:
            bucket.count, bucket.started_at = 0, at
        result.append(bucket)
    return result


def require_under_limit(items: list[AuthThrottle], limits: list[int], at: datetime) -> None:
    for item, limit in zip(items, limits, strict=True):
        if item.count >= limit:
            retry = max(1, math.ceil((item.started_at + RATE_WINDOW - at).total_seconds()))
            raise DomainError(429, "rate_limited", "Za dużo prób. Spróbuj ponownie później.", retry)


async def credential(
    db: AsyncSession, request: Request, player: Player | None, profile_id: UUID, pin: str
) -> Player:
    at = now(request)
    items = await buckets(db, [f"pin:{profile_id}", f"source:{source_address(request)}"], at)
    require_under_limit(items, [5, 30], at)
    valid = await verify_pin(player.pin_hash if player and player.is_active else DUMMY_HASH, pin)
    if not player or not player.is_active or not valid:
        for item in items:
            item.count += 1
        # Failed attempts must survive the error response and a process restart.
        await db.commit()
        raise DomainError(401, "invalid_credentials", "Nieprawidłowy profil lub PIN.")
    items[0].count = 0
    if HASHER.check_needs_rehash(player.pin_hash):
        player.pin_hash = await hash_pin(pin)
    return player


async def rate_action(db: AsyncSession, request: Request, kind: str, limit: int = 10) -> None:
    items = await buckets(db, [f"{kind}:{source_address(request)}"], now(request))
    require_under_limit(items, [limit], now(request))
    items[0].count += 1
    # Callers commit on successful creation and also before invalid-token errors.


async def invalid_token(db: AsyncSession) -> None:
    await db.commit()
    raise DomainError(
        400, "invalid_token", "Link jest nieprawidłowy, wygasł lub został wykorzystany."
    )
