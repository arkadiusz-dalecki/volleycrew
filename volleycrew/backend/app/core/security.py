import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings

SESSION_COOKIE = "vc_session"
CSRF_COOKIE = "vc_csrf"
AUTH_LOCK = 82471601
IDLE = timedelta(days=30)
ABSOLUTE = timedelta(days=180)
RESET_TTL = timedelta(minutes=30)
RATE_WINDOW = timedelta(minutes=15)
HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(12))


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def load_auth_key(settings: Settings) -> bytes:
    if settings.session_secret:
        return settings.session_secret.get_secret_value().encode()
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    path = settings.state_dir / "auth.key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        value = path.read_bytes()
    else:
        value = secrets.token_bytes(32)
        with os.fdopen(fd, "wb") as file:
            file.write(value)
    if len(value) < 32:
        raise RuntimeError("Invalid persistent auth key")
    return value


async def hash_pin(pin: str) -> str:
    return await run_in_threadpool(HASHER.hash, pin)


async def verify_pin(encoded: str, pin: str) -> bool:
    def verify() -> bool:
        try:
            return HASHER.verify(encoded, pin)
        except (VerificationError, InvalidHashError):
            return False

    return await run_in_threadpool(verify)


def csrf_token(key: bytes, session_token: str, now: datetime) -> str:
    payload = f"{new_token()}.{int((now + timedelta(days=1)).timestamp())}"
    signature = hmac.new(
        key, f"{token_hash(session_token)}:{payload}".encode(), "sha256"
    ).hexdigest()
    return f"{payload}.{signature}"


def valid_csrf(value: str, key: bytes, session_token: str, now: datetime) -> bool:
    try:
        nonce, deadline, signature = value.split(".")
        if len(nonce) != 43 or int(deadline) <= now.timestamp():
            return False
        expected = hmac.new(
            key, f"{token_hash(session_token)}:{nonce}.{deadline}".encode(), "sha256"
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (ValueError, TypeError):
        return False


def cookie_name(request: Request, name: str) -> str:
    return name + ("_ingress" if request.scope.get("root_path") else "")


def cookie_path(request: Request) -> str:
    return request.scope.get("root_path", "").rstrip("/") + "/"


def set_csrf(response: Response, request: Request, session_token: str, now: datetime) -> str:
    value = csrf_token(request.app.state.auth_key, session_token, now)
    response.set_cookie(
        cookie_name(request, CSRF_COOKIE),
        value,
        max_age=86400,
        secure=request.app.state.settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path=cookie_path(request),
    )
    return value


def allowed_origins(settings: Settings) -> set[str]:
    url = urlsplit(settings.public_url)
    origins = {f"{url.scheme}://{url.netloc}", *settings.additional_origins}
    if not settings.cookie_secure and url.hostname in {"localhost", "127.0.0.1"}:
        origins |= {f"http://localhost:{url.port or 80}", f"http://127.0.0.1:{url.port or 80}"}
    return origins


def source_address(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    networks = [ip_network(cidr) for cidr in request.app.state.settings.trusted_proxy_cidrs]

    def trusted(address: str) -> bool:
        try:
            return any(ip_address(address) in network for network in networks)
        except ValueError:
            return False

    if trusted(peer):
        chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",")]
        for address in reversed(chain):
            try:
                ip_address(address)
            except ValueError:
                return peer
            if not trusted(address):
                return address
    return peer
