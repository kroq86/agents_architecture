"""Transactional outbox: POST /chat/async and worker."""

import pytest


@pytest.mark.integration
@pytest.mark.e2e
def test_chat_async_returns_202_with_queued_status(client):
    r = client.post("/chat/async", json={"message": "enqueue me"})
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["run_id"]
    assert data["request_id"]
    assert data["trace_id"]

