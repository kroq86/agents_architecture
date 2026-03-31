"""Explicit tool execution boundary: registry + policy + retry + metrics."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from opentelemetry import trace
from pydantic import BaseModel

from app.core.config import get_settings
from app.observability.metrics import TOOL_CALL_COUNT, TOOL_LATENCY_SECONDS
from app.services.retry import retry_async
from app.services.runtime_policy import allowed_tool_names_for_task_type, is_tool_allowed_for_task
from app.tools.base import Tool, ToolPolicy, ToolRegistry, ToolResult

tracer = trace.get_tracer(__name__)

SingleAttemptFn = Callable[[Tool, BaseModel], Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolGatewayResult:
    """Outcome of a single tool invocation through the gateway."""

    registered: bool
    tool_name: str
    args: dict[str, Any]
    normalized: ToolResult | None
    """Populated when the tool ran successfully (includes policy-normalized envelope)."""
    unregistered_message: str | None = None
    """Set when the tool name is not in the registry or policy blocks the call."""
    policy_denied: bool = False
    """True when the tool exists but ``task_type`` allowlist forbids this tool."""


class ToolGateway:
    """Wraps ``ToolRegistry`` + ``ToolPolicy``; orchestrator calls this instead of tools directly."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy or ToolPolicy()
        self._max_retry_attempts = get_settings().max_retry_attempts

    def list_specs(self) -> list[dict[str, Any]]:
        return self._registry.list_specs()

    def list_specs_for_task(self, task_type: str) -> list[dict[str, Any]]:
        """Prompt-visible tool inventory for ``task_type`` (architecture §9.6 minimal)."""
        all_specs = self._registry.list_specs()
        allowed = allowed_tool_names_for_task_type(task_type)
        if allowed is None:
            return all_specs
        return [s for s in all_specs if s.get("name") in allowed]

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        task_type: str = "chat",
        single_attempt: SingleAttemptFn | None = None,
    ) -> ToolGatewayResult:
        tool = self._registry.get(tool_name)
        if tool is None:
            return ToolGatewayResult(
                registered=False,
                policy_denied=False,
                tool_name=tool_name,
                args=args,
                normalized=None,
                unregistered_message=f"Requested tool '{tool_name}' is not registered.",
            )

        if not is_tool_allowed_for_task(task_type, tool_name):
            return ToolGatewayResult(
                registered=True,
                policy_denied=True,
                tool_name=tool_name,
                args=args,
                normalized=None,
                unregistered_message=(
                    f"Tool '{tool_name}' is not permitted for task_type '{task_type}'."
                ),
            )

        self._policy.pre_execute(tool_name, args)
        parsed = tool.input_schema.model_validate(args)

        async def run_attempt() -> ToolResult:
            if single_attempt is not None:
                return await single_attempt(tool, parsed)
            return await tool.execute(parsed)

        with tracer.start_as_current_span("tool.execute"):
            tool_start = time.perf_counter()
            raw = await retry_async(
                operation="tool.execute",
                max_attempts=self._max_retry_attempts,
                call=run_attempt,
            )
            TOOL_LATENCY_SECONDS.labels(tool_name=tool_name).observe(time.perf_counter() - tool_start)

        normalized = self._policy.normalize_result(cast(ToolResult, raw))
        TOOL_CALL_COUNT.labels(
            tool_name=tool_name,
            status="success" if normalized.get("success") else "error",
        ).inc()

        return ToolGatewayResult(
            registered=True,
            policy_denied=False,
            tool_name=tool_name,
            args=args,
            normalized=normalized,
        )
