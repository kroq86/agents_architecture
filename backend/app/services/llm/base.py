from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal
from typing import Any


@dataclass
class LLMReply:
    action: Literal["finish", "tool_call"]
    text: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str, tools: list[dict[str, Any]]) -> LLMReply:
        raise NotImplementedError

