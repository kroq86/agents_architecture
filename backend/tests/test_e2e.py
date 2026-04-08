"""End-to-end tests: full HTTP + DB paths via TestClient (in-process ASGI).

For a live-server guard against ``doc.md``, see ``backend/scripts/e2e_doc_guard.py``.
"""

from __future__ import annotations

import pytest

from tests.e2e_helpers import REPO_ROOT, doc_md_exists, sse_run_completed_run_id


@pytest.mark.e2e
def test_e2e_sync_chat_sse_completes_run(client):
    """POST /chat streams SSE; run completes and is readable via GET /runs/{id}."""
    with client.stream("POST", "/chat", json={"message": "hello e2e sync"}) as r:
        assert r.status_code == 200
        body = r.read().decode("utf-8", errors="replace")

    rid = sse_run_completed_run_id(body)
    assert rid, f"expected run_completed in SSE body, got: {body[:500]!r}"

    gr = client.get(f"/runs/{rid}")
    assert gr.status_code == 200
    data = gr.json()
    assert data["status"] == "completed"
    assert len(data["messages"]) >= 2
    roles = [m["role"] for m in data["messages"]]
    assert "user" in roles and "assistant" in roles


@pytest.mark.e2e
@pytest.mark.skipif(not doc_md_exists(), reason="doc.md missing at repo root")
def test_e2e_search_documents_touches_doc_md(client):
    """Same intent as ``backend/scripts/e2e_doc_guard.py``: tool hits doc.md corpus."""
    payload = {
        "message": (
            'You must call search_documents with query="Если хочешь следующий шаг" '
            "and answer with that exact line."
        ),
        "session_id": "e2e-doc-session",
        "task_type": "research",
        "user_constraints": {"must_use_tool": True},
        "priority": "high",
    }
    with client.stream("POST", "/chat", json=payload) as r:
        assert r.status_code == 200
        body = r.read().decode("utf-8", errors="replace")

    rid = sse_run_completed_run_id(body)
    assert rid

    run = client.get(f"/runs/{rid}").json()
    tool_calls = run.get("tool_calls") or []
    assert tool_calls, "expected at least one tool_call (search_documents)"

    call = tool_calls[0]
    assert call.get("tool_name") == "search_documents"
    out = call.get("tool_output") or {}
    meta = out.get("metadata") or {}
    source = meta.get("source") or ""
    assert source.endswith("/doc.md") or (REPO_ROOT / "doc.md").as_posix() in source

    payload_out = out.get("payload") or {}
    matches = payload_out.get("matches") or []
    assert len(matches) >= 1

