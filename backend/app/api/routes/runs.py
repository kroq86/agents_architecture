from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import MessageRead, RunRead, ToolCallRead, TranscriptEventRead
from app.db.session import get_session
from app.services.repositories.runs import RunRepository

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> RunRead:
    repo = RunRepository(session)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    events = sorted(run.transcript_events, key=lambda e: e.seq)
    return RunRead(
        id=run.id,
        request_id=run.request_id,
        session_id=run.session_id,
        trace_id=run.trace_id,
        task_type=run.task_type,
        status=run.status,
        created_at=run.created_at,
        finished_at=run.finished_at,
        messages=[
            MessageRead(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
            for m in run.messages
        ],
        tool_calls=[
            ToolCallRead(
                id=t.id,
                tool_name=t.tool_name,
                tool_input=t.tool_input,
                tool_output=t.tool_output,
                created_at=t.created_at,
            )
            for t in run.tool_calls
        ],
        transcript_events=[
            TranscriptEventRead(
                id=e.id,
                seq=e.seq,
                kind=e.kind,
                payload=e.payload_json,
                created_at=e.created_at,
            )
            for e in events
        ],
    )

