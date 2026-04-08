"""E2E coverage for transactional outbox: enqueue, DB rows, worker, metrics, SLA timing."""

from __future__ import annotations

import time

import pytest
from sqlalchemy import select

import app.worker.main as worker_main
from app.db.session import get_session_factory
from app.models.outbox_event import OutboxEvent
from app.worker.main import process_one
from tests.e2e_helpers import (
    prometheus_counter_sum,
    prometheus_histogram_mean_seconds,
    prometheus_histogram_total_sum_count,
)


class _FailingOrchestrator:
    async def execute_existing_run(self, session, run_id):  # pragma: no cover - generator shape only
        raise RuntimeError("forced outbox failure")
        yield {"event": "never"}


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_outbox_full_flow_db_metrics_and_sla(client):
    """Covers: pending outbox + queued run → worker → processed outbox + completed run + Prometheus."""
    metrics_before = client.get("/metrics").text
    proc_before = prometheus_counter_sum(metrics_before, "app_outbox_events_processed_total")
    pipe_sum_before, pipe_count_before = prometheus_histogram_total_sum_count(
        metrics_before, "app_outbox_pipeline_seconds"
    )

    t0 = time.perf_counter()

    r = client.post("/chat/async", json={"message": "outbox e2e full flow"})
    assert r.status_code == 202
    rid = r.json()["run_id"]

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.run_id == rid))
        ev = result.scalar_one()
        assert ev.status == "pending"
        assert ev.event_type == "run_created"

    gr0 = client.get(f"/runs/{rid}")
    assert gr0.json()["status"] == "queued"

    assert await process_one() is True
    assert await process_one() is False

    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0, f"enqueue→completed SLA wall clock too slow: {elapsed:.2f}s"

    gr = client.get(f"/runs/{rid}")
    assert gr.status_code == 200
    assert gr.json()["status"] == "completed"

    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.run_id == rid))
        ev2 = result.scalar_one()
        assert ev2.status == "processed"
        assert ev2.processed_at is not None

    metrics_text = client.get("/metrics").text
    proc_after = prometheus_counter_sum(metrics_text, "app_outbox_events_processed_total")
    assert proc_after >= proc_before + 1.0
    pipe_sum_after, pipe_count_after = prometheus_histogram_total_sum_count(
        metrics_text, "app_outbox_pipeline_seconds"
    )
    assert pipe_count_after >= pipe_count_before + 1.0
    delta_sum = pipe_sum_after - pipe_sum_before
    delta_count = pipe_count_after - pipe_count_before
    assert delta_count >= 1.0
    assert 0.0 <= delta_sum / delta_count < 30.0

    mean_s = prometheus_histogram_mean_seconds(metrics_text, "app_outbox_pipeline_seconds")
    assert mean_s is not None
    assert 0.0 <= mean_s < 30.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_outbox_two_runs_sequential_worker_drains_queue(client):
    """Two enqueues produce two outbox rows; two process_one calls complete both."""
    metrics_before = client.get("/metrics").text
    proc_before = prometheus_counter_sum(metrics_before, "app_outbox_events_processed_total")

    r1 = client.post("/chat/async", json={"message": "first queue item"})
    r2 = client.post("/chat/async", json={"message": "second queue item"})
    assert r1.status_code == 202 and r2.status_code == 202
    id1, id2 = r1.json()["run_id"], r2.json()["run_id"]

    assert await process_one() is True
    assert await process_one() is True
    assert await process_one() is False

    assert client.get(f"/runs/{id1}").json()["status"] == "completed"
    assert client.get(f"/runs/{id2}").json()["status"] == "completed"

    metrics_text = client.get("/metrics").text
    assert prometheus_counter_sum(metrics_text, "app_outbox_events_processed_total") >= proc_before + 2.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_outbox_failure_marks_retryable_and_run_failed(client, monkeypatch):
    """Worker failure marks outbox retryable and run failed."""
    monkeypatch.setattr(worker_main, "get_orchestrator", lambda: _FailingOrchestrator())

    r = client.post("/chat/async", json={"message": "force retryable status"})
    assert r.status_code == 202
    rid = r.json()["run_id"]

    assert await worker_main.process_one() is True
    assert await worker_main.process_one() is False

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.run_id == rid))
        ev = result.scalar_one()
        assert ev.status == "retryable"
        assert ev.next_retry_at is not None

    run = client.get(f"/runs/{rid}").json()
    assert run["status"] == "failed"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_outbox_failure_marks_dead_and_increments_dead_counter(client, monkeypatch):
    """When max_attempts is reached, worker marks outbox dead and bumps dead counter."""
    monkeypatch.setattr(worker_main, "get_orchestrator", lambda: _FailingOrchestrator())
    dead_before = prometheus_counter_sum(client.get("/metrics").text, "app_outbox_events_dead_total")

    r = client.post("/chat/async", json={"message": "force dead status"})
    assert r.status_code == 202
    rid = r.json()["run_id"]

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.run_id == rid))
        ev = result.scalar_one()
        ev.max_attempts = 1
        await session.commit()

    assert await worker_main.process_one() is True

    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.run_id == rid))
        ev2 = result.scalar_one()
        assert ev2.status == "dead"
        assert ev2.error_message is not None

    run = client.get(f"/runs/{rid}").json()
    assert run["status"] == "failed"
    dead_after = prometheus_counter_sum(client.get("/metrics").text, "app_outbox_events_dead_total")
    assert dead_after >= dead_before + 1.0
