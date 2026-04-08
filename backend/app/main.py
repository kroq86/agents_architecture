from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware

from app.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes.chat import router as chat_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.runs import router as runs_router
from app.core.config import get_settings
from app.db.session import dispose_engine, get_session
from app.limiter import limiter
from app.observability.metrics import metrics_middleware, metrics_response
from app.observability.tracing import configure_tracing
from starlette.exceptions import HTTPException as StarletteHTTPException


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await dispose_engine()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    configure_tracing(app, settings)
    app.middleware("http")(metrics_middleware)

    origins = settings.cors_origins_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(chat_router, tags=["chat"])
    app.include_router(runs_router, tags=["runs"])
    app.include_router(reviews_router, tags=["reviews"])

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        return metrics_response()

    return app


app = create_app()
