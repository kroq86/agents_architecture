"""Poll outbox_events and execute queued runs (separate process from API)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timezone

from app.api.deps import get_orchestrator
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.outbox_event import OutboxEvent
from app.observability.metrics import (
    OUTBOX_EVENTS_DEAD,
    OUTBOX_EVENTS_PROCESSED,
    OUTBOX_PIPELINE_SECONDS,
)
from app.services.repositories.outbox import OutboxRepository
from app.services.repositories.runs import RunRepository

logger = logging.getLogger(__name__)


def _observe_pipeline_sla(ev: OutboxEvent, event_type: str) -> None:
    """Histogram: seconds from outbox row creation to successful processing."""
    created = ev.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    elapsed = max(0.0, time.time() - created.timestamp())
    OUTBOX_PIPELINE_SECONDS.labels(event_type=event_type).observe(elapsed)


async def process_one() -> bool:
    """Claim at most one outbox row and process it. Returns True if work was done."""
    settings = get_settings()
    factory = get_session_factory()
    orch = get_orchestrator()

    async with factory() as session:
        async with session.begin():
            ob = OutboxRepository(session)
            ev = await ob.claim_next(settings.worker_id, settings.outbox_lease_seconds)

    if ev is None or not ev.run_id:
        return False

    eid = ev.id
    rid = ev.run_id
    event_type = ev.event_type

    try:
        async with factory() as session:
            async for _ in orch.execute_existing_run(session, rid):
                pass

        async with factory() as session:
            async with session.begin():
                ob = OutboxRepository(session)
                ev2 = await session.get(OutboxEvent, eid)
                if ev2:
                    await ob.mark_processed(ev2)
        OUTBOX_EVENTS_PROCESSED.labels(event_type=event_type).inc()
        _observe_pipeline_sla(ev, event_type)
        return True

    except Exception as ex:
        logger.exception("outbox processing failed run_id=%s", rid)
        async with factory() as session:
            async with session.begin():
                ob = OutboxRepository(session)
                ev2 = await session.get(OutboxEvent, eid)
                if ev2:
                    await ob.mark_failure(
                        ev2,
                        error_message=str(ex)[:2000],
                        max_attempts=ev2.max_attempts,
                        backoff_seconds=settings.outbox_retry_backoff_seconds,
                    )
                    if ev2.status == "dead":
                        OUTBOX_EVENTS_DEAD.labels(event_type=event_type).inc()
                rr = RunRepository(session)
                run = await rr.get_run(rid)
                if run and run.status not in ("completed", "failed"):
                    await rr.fail_run(run, str(ex)[:2000])
        return True


async def main_loop() -> None:
    settings = get_settings()
    while True:
        worked = await process_one()
        if not worked:
            await asyncio.sleep(settings.worker_poll_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
