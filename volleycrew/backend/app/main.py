from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.enrollment import router as enrollment_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.results import router as results_router
from app.api.room import router as room_router
from app.api.schedule_changes import router as schedule_router
from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.database import Database
from app.core.proxy import ProxyContext
from app.core.security import load_auth_key


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = Database(settings.database_url.get_secret_value())
        app.state.clock = clock or SystemClock()
        app.state.settings = settings
        app.state.auth_key = load_auth_key(settings)
        try:
            yield
        finally:
            await app.state.database.engine.dispose()

    app = FastAPI(title="Volleycrew API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(ProxyContext, enabled=settings.behind_proxy)
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(meetings_router, prefix="/api/v1")
    app.include_router(enrollment_router, prefix="/api/v1")
    app.include_router(schedule_router, prefix="/api/v1")
    app.include_router(room_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(results_router, prefix="/api/v1")

    @app.middleware("http")
    async def no_auth_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app


app = create_app()
