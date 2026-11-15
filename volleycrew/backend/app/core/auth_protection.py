"""Bounded admission and secret-free telemetry; durable PIN limits remain in PostgreSQL."""

import hashlib
import hmac
import json
import logging
import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import get_route_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.security import source_address

OPERATIONS = {
    "/api/v1/auth/login": "login",
    "/api/v1/auth/google/start": "google_start",
    "/api/v1/auth/google/callback": "google_callback",
    "/api/v1/auth/register": "registration",
    "/api/v1/auth/bootstrap": "bootstrap",
    "/api/v1/auth/reset-pin": "reset",
}


@dataclass
class Bucket:
    tokens: float
    at: float

    def refill(self, at: float, rate: float, burst: int) -> float:
        self.tokens = min(burst, self.tokens + max(0, at - self.at) * rate)
        self.at = at
        return max(0, (1 - self.tokens) / rate)


class AuthAdmission:
    """Single-worker burst protection, before parsing bodies, DB access or hashing.

    Per-source: burst 10, refill 30/minute. Entire process: burst 20, refill 4/second.
    Eviction/restart affects only this additional gate, never durable attempt counts.
    """

    def __init__(self, timer: Callable[[], float] = time.monotonic):
        self.timer = timer
        self.global_bucket = Bucket(20, timer())
        self.sources: OrderedDict[str, Bucket] = OrderedDict()

    def check(self, source: str) -> int:
        at = self.timer()
        bucket = self.sources.pop(source, Bucket(10, at))
        self.sources[source] = bucket
        if len(self.sources) > 1024:
            self.sources.popitem(last=False)
        wait = max(bucket.refill(at, 0.5, 10), self.global_bucket.refill(at, 4, 20))
        if wait > 0:
            return max(1, math.ceil(wait))
        bucket.tokens -= 1
        self.global_bucket.tokens -= 1
        return 0


class SecurityMonitor:
    """At most 60 event entries + one suppression marker per minute per process."""

    def __init__(self, key: bytes, timer: Callable[[], float] = time.monotonic):
        self.key, self.timer = key, timer
        self.started_at, self.count = timer(), 0

    def record(self, event: str, operation: str, source: str) -> None:
        at = self.timer()
        if at >= self.started_at + 60:
            self.started_at, self.count = at, 0
        self.count += 1
        if self.count > 61:
            return
        if self.count == 61:
            entry = {"event": "security_logs_suppressed"}
        else:
            # Keyed fingerprint allows correlation without logging raw addresses.
            fingerprint = hmac.new(
                self.key, f"security-source:{source}".encode(), hashlib.sha256
            ).hexdigest()[:20]
            entry = {"event": event, "operation": operation, "source": fingerprint}
        entry["at"] = datetime.now(UTC).isoformat()
        logging.getLogger("volleycrew.security").info(json.dumps(entry, sort_keys=True))


class AuthProtection:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.admission = AuthAdmission()
        self.callback_admission = AuthAdmission()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = get_route_path(scope).rstrip("/")
        if scope["method"] != "POST" and not (
            scope["method"] == "GET" and path == "/api/v1/auth/google/callback"
        ):
            await self.app(scope, receive, send)
            return
        operation = OPERATIONS.get(path)
        if not operation:
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        source = source_address(request)
        monitor = request.app.state.security_monitor
        is_callback = scope["method"] == "GET"
        gate = self.callback_admission if is_callback else self.admission
        retry = gate.check(source)
        if retry:
            monitor.record("auth_burst_limited", operation, source)
            if is_callback:
                response = RedirectResponse(
                    request.app.state.settings.public_url + "/login#google=limited",
                    303,
                    headers={"Retry-After": str(retry)},
                )
                await response(scope, receive, send)
                return
            await JSONResponse(
                {"code": "rate_limited", "message": "Za dużo prób. Spróbuj ponownie później."},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )(scope, receive, send)
            return

        async def observe(message: Message) -> None:
            if message["type"] == "http.response.start":
                event = {
                    200: "auth_succeeded",
                    400: "auth_invalid_link",
                    401: "auth_failed",
                    403: "auth_csrf_rejected",
                    422: "auth_invalid_input",
                    429: "auth_rate_limited",
                }.get(message["status"])
                if event:
                    monitor.record(event, operation, source)
            await send(message)

        await self.app(scope, receive, observe)
