#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request


CHAT_URL = "http://127.0.0.1:8000/chat"
RUN_URL_TEMPLATE = "http://127.0.0.1:8000/runs/{run_id}"
DOC_PATH_SUFFIX = "/doc.md"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def post_chat() -> str:
    payload = {
        "message": (
            'You must call search_documents with query="Если хочешь следующий шаг" '
            "and answer with that exact line."
        ),
        "session_id": "guard-doc-session",
        "task_type": "research",
        "user_constraints": {"must_use_tool": True},
        "priority": "high",
    }
    req = urllib.request.Request(
        CHAT_URL,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        fail(f"/chat request failed: {exc}")

    run_id = None
    event = None
    for line in body.splitlines():
        if line.startswith("event: "):
            event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data: ") and event == "run_completed":
            raw = line.split(":", 1)[1].strip()
            run_id = json.loads(raw)
            break
    if not run_id:
        fail("could not extract run_completed id from SSE response")
    return run_id


def get_run(run_id: str) -> dict:
    url = RUN_URL_TEMPLATE.format(run_id=run_id)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        fail(f"/runs fetch failed: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"/runs response is not valid JSON: {exc}")


def validate(run_payload: dict) -> None:
    tool_calls = run_payload.get("tool_calls") or []
    if not tool_calls:
        fail("tool_calls is empty; expected search_documents to execute")

    call = tool_calls[0]
    if call.get("tool_name") != "search_documents":
        fail(f"unexpected tool_name: {call.get('tool_name')}")

    tool_output = call.get("tool_output") or {}
    metadata = tool_output.get("metadata") or {}
    source = metadata.get("source") or ""
    if not source.endswith(DOC_PATH_SUFFIX):
        fail(f"tool source is not doc.md: {source}")

    payload = tool_output.get("payload") or {}
    matches = payload.get("matches") or []
    if len(matches) < 1:
        fail("no matches returned from doc.md search")

    print("PASS: doc.md E2E guard succeeded")
    print(f"run_id={run_payload.get('id')}")
    print(f"source={source}")
    print(f"matches={len(matches)}")


def main() -> None:
    run_id = post_chat()
    run_payload = get_run(run_id)
    validate(run_payload)


if __name__ == "__main__":
    main()

