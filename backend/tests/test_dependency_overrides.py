"""Examples of FastAPI `dependency_overrides` for tests."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_orchestrator
from app.main import create_app


@pytest.mark.integration
def test_chat_stream_uses_overridden_orchestrator():
    """Override `get_orchestrator` so `/chat` does not call the real agent loop."""

    class FakeOrchestrator:
        async def run(self, session, request):
            yield {"event": "message", "data": {"text": "stub"}}

    app = create_app()
    app.dependency_overrides[get_orchestrator] = lambda: FakeOrchestrator()
    with TestClient(app) as client:
        with client.stream("POST", "/chat", json={"message": "hi"}) as r:
            assert r.status_code == 200
            body = r.read()
    assert b"stub" in body
