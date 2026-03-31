"""Deterministic runtime policy (architecture §5.6): rules enforced outside prompts only."""

from __future__ import annotations

# If task_type is absent from this map, any tool registered in the gateway may be used.
_TASK_TYPE_TOOL_ALLOWLIST: dict[str, frozenset[str]] = {
    "chat": frozenset({"search_documents"}),
    "research": frozenset({"search_documents"}),
}


def allowed_tool_names_for_task_type(task_type: str) -> frozenset[str] | None:
    """Return allowed tool names for ``task_type``, or ``None`` if any registered tool is allowed."""
    return _TASK_TYPE_TOOL_ALLOWLIST.get(task_type)


def is_tool_allowed_for_task(task_type: str, tool_name: str) -> bool:
    allowed = allowed_tool_names_for_task_type(task_type)
    if allowed is None:
        return True
    return tool_name in allowed
