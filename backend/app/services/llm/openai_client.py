import json

from openai import AsyncOpenAI

from app.core.config import Settings
from app.services.llm.base import LLMClient, LLMReply


class OpenAILLMClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        self._model = settings.openai_model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._price_map = settings.model_price_map()

    async def complete(self, prompt: str, tools: list[dict]) -> LLMReply:
        tools_text = json.dumps(tools)
        full_prompt = f"{prompt}\n\nAvailable tools:\n{tools_text}"
        resp = await self._client.responses.create(
            model=self._model,
            input=full_prompt,
        )
        text = resp.output_text.strip()
        usage = getattr(resp, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        estimated_cost = self._estimate_cost(self._model, input_tokens, output_tokens)
        tool_call = self._try_parse_tool_call(text)
        if tool_call:
            return LLMReply(
                action="tool_call",
                text=text,
                tool_name=tool_call["tool_name"],
                tool_args=tool_call["args"],
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
            )
        return LLMReply(
            action="finish",
            text=text,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
        )

    @staticmethod
    def _try_parse_tool_call(content: str) -> dict | None:
        if not content.startswith("TOOL_CALL:"):
            return None
        try:
            payload = content.split(":", 1)[1].strip()
            parsed = json.loads(payload)
            if "tool_name" not in parsed or "args" not in parsed:
                return None
            return parsed
        except json.JSONDecodeError:
            return None

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        model_prices = self._price_map.get(model, {})
        input_per_1k = float(model_prices.get("input_per_1k", 0))
        output_per_1k = float(model_prices.get("output_per_1k", 0))
        return ((input_tokens / 1000.0) * input_per_1k) + ((output_tokens / 1000.0) * output_per_1k)

