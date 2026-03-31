import json
import time

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_orchestrator
from app.core.config import get_settings
from app.core.schemas import ChatRequest
from app.db.session import get_session
from app.limiter import limiter
from app.observability.metrics import CHAT_STREAM_DURATION_SECONDS
from app.services.agent.orchestrator import AgentOrchestrator

router = APIRouter()

_settings = get_settings()
_CHAT_RATE = _settings.chat_rate_limit if _settings.rate_limit_enabled else "1000000/minute"


@router.post("/chat")
@limiter.limit(_CHAT_RATE)
async def chat(
    request: Request,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> EventSourceResponse:
    internal_request = payload.to_internal_request()

    async def event_gen():
        start = time.perf_counter()
        outcome = "completed"
        try:
            async for chunk in orchestrator.run(
                session=session,
                request=internal_request,
            ):
                yield {"event": chunk["event"], "data": json.dumps(chunk["data"])}
        except Exception:
            outcome = "error"
            raise
        finally:
            CHAT_STREAM_DURATION_SECONDS.labels(outcome=outcome).observe(time.perf_counter() - start)

    return EventSourceResponse(event_gen())

