from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox_event import OutboxEvent


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_run_created(
        self,
        *,
        run_id: str,
        request_id: str,
        trace_id: str,
        payload_json: dict[str, Any],
    ) -> OutboxEvent:
        ev = OutboxEvent(
            event_type="run_created",
            event_schema_version=1,
            aggregate_type="run",
            aggregate_id=run_id,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            payload_json=payload_json,
            status="pending",
        )
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def get_by_id(self, event_id: str) -> OutboxEvent | None:
        return await self.session.get(OutboxEvent, event_id)

    async def claim_next(
        self,
        worker_id: str,
        lease_seconds: int,
    ) -> OutboxEvent | None:
        """Pick one pending/retryable row with SKIP LOCKED and lease it."""
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)
        ready_at = func.coalesce(OutboxEvent.next_retry_at, OutboxEvent.available_at)

        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status.in_(("pending", "retryable")),
                ready_at <= now,
                or_(
                    OutboxEvent.lease_expires_at.is_(None),
                    OutboxEvent.lease_expires_at < now,
                ),
            )
            .order_by(OutboxEvent.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        ev = result.scalar_one_or_none()
        if ev is None:
            return None
        ev.status = "processing"
        ev.lease_owner = worker_id
        ev.lease_expires_at = lease_until
        ev.attempt_count += 1
        await self.session.flush()
        return ev

    async def mark_processed(self, event: OutboxEvent) -> None:
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        event.lease_owner = None
        event.lease_expires_at = None
        await self.session.flush()

    async def mark_failure(
        self,
        event: OutboxEvent,
        *,
        error_message: str,
        max_attempts: int,
        backoff_seconds: int,
    ) -> None:
        if event.attempt_count >= max_attempts:
            event.status = "dead"
            event.error_message = error_message
        else:
            event.status = "retryable"
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            event.error_message = error_message
        event.lease_owner = None
        event.lease_expires_at = None
        await self.session.flush()
