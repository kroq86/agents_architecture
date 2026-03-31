from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


ToolResult = dict[str, Any]


class ErrorCategory(StrEnum):
    TRANSIENT = "transient"
    VALIDATION = "validation"
    BUSINESS = "business"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class Tool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, payload: BaseModel) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for tool in self._tools.values():
            specs.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema.model_json_schema(),
                }
            )
        return specs


class ToolPolicy:
    def pre_execute(self, tool_name: str, args: dict[str, Any]) -> None:
        if not tool_name:
            raise ValueError("Tool name is required")
        if not isinstance(args, dict):
            raise ValueError("Tool args must be an object")

    def normalize_result(self, result: ToolResult) -> ToolResult:
        raw_category = result.get("error_category")
        if raw_category is None:
            error_category = None
        elif raw_category in {e.value for e in ErrorCategory}:
            error_category = raw_category
        else:
            error_category = ErrorCategory.UNKNOWN.value
        return {
            "success": bool(result.get("success", False)),
            "is_error": bool(result.get("is_error", False)),
            "error_category": error_category,
            "is_retryable": bool(result.get("is_retryable", False)),
            "result_type": result.get("result_type", "generic"),
            "payload": result.get("payload", {}),
            "metadata": result.get("metadata", {}),
            "partial_results": result.get("partial_results", []),
            "attempted_action": result.get("attempted_action"),
            "suggested_next_steps": result.get("suggested_next_steps", []),
        }

