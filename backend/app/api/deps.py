from functools import lru_cache

from app.core.config import get_settings
from app.services.agent.orchestrator import AgentOrchestrator
from app.services.tool_gateway import ToolGateway
from app.services.llm.base import LLMClient
from app.services.llm.mock_client import MockLLMClient
from app.services.llm.openai_client import OpenAILLMClient
from app.tools.base import ToolRegistry
from app.tools.search_documents import SearchDocumentsTool


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry([SearchDocumentsTool()])


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMClient()
    return OpenAILLMClient(settings)


@lru_cache(maxsize=1)
def get_tool_gateway() -> ToolGateway:
    return ToolGateway(get_tool_registry())


def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(llm=get_llm_client(), tool_gateway=get_tool_gateway())

