from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes.chat import router as chat_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.runs import router as runs_router
from app.core.config import get_settings
from app.limiter import limiter
from app.observability.metrics import metrics_middleware, metrics_response
from app.observability.tracing import configure_tracing


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    configure_tracing(app, settings)
    app.middleware("http")(metrics_middleware)
    app.include_router(chat_router, tags=["chat"])
    app.include_router(runs_router, tags=["runs"])
    app.include_router(reviews_router, tags=["reviews"])

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        return metrics_response()

    return app


app = create_app()

