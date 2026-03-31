import json

from app.services.llm.base import LLMClient, LLMReply


class MockLLMClient(LLMClient):
    async def complete(self, prompt: str, tools: list[dict]) -> LLMReply:
        if "search" in prompt.lower():
            return LLMReply(
                action="tool_call",
                text='TOOL_CALL: {"tool_name":"search_documents","args":{"query":"mock query"}}',
                tool_name="search_documents",
                tool_args={"query": "mock query"},
                model="mock",
            )
        return LLMReply(action="finish", text="Mock final response.", model="mock")

    @staticmethod
    def parse_tool_line(content: str) -> dict | None:
        if not content.startswith("TOOL_CALL:"):
            return None
        payload = content.split(":", 1)[1].strip()
        return json.loads(payload)

