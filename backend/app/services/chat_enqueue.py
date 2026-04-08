"""Enqueue a chat run + outbox row in one transaction (async processing path)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import InternalRequest
from app.models.run import Run
from app.services.repositories.outbox import OutboxRepository
from app.services.repositories.runs import RunRepository
from app.services.repositories.state import SessionStateRepository


async def enqueue_chat_run(session: AsyncSession, request: InternalRequest) -> Run:
    """Create queued run, user message, transcript, session fact, and outbox `run_created` in one transaction."""
    repo = RunRepository(session)
    state_repo = SessionStateRepository(session)
    ob = OutboxRepository(session)
    user_id = request.input_payload.get("user_id")
    user_input = request.input_payload.get("message", "")

    async with session.begin():
        state = await state_repo.get_or_create(request.session_id)
        run = await repo.create_run(
            user_id=user_id,
            input_text=user_input,
            request_id=request.request_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            task_type=request.task_type,
            user_constraints=request.user_constraints,
            priority=request.priority,
            deadline=request.deadline,
            attachments=request.attachments,
            status="queued",
        )
        await repo.add_message(run.id, "user", user_input)
        await repo.append_transcript_event(run.id, "user", {"text": user_input})
        await state_repo.upsert_fact(
            state.id,
            key="last_user_input",
            value={"text": user_input, "request_id": request.request_id},
        )
        await ob.insert_run_created(
            run_id=run.id,
            request_id=request.request_id,
            trace_id=request.trace_id,
            payload_json=request.model_dump(),
        )
    return run
