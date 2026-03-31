from functools import lru_cache
import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_name: str = Field(default="minimal-local-ai-agent", alias="APP_NAME")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./local.db",
        alias="DATABASE_URL",
    )

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    otel_service_name: str = Field(
        default="minimal-local-ai-agent",
        alias="OTEL_SERVICE_NAME",
    )
    otel_traces_exporter: str = Field(default="console", alias="OTEL_TRACES_EXPORTER")
    max_retry_attempts: int = Field(default=2, alias="MAX_RETRY_ATTEMPTS")
    max_tool_calls_per_run: int = Field(default=1, ge=1, alias="MAX_TOOL_CALLS_PER_RUN")
    openai_model_prices_json: str = Field(
        default='{"gpt-4.1-mini":{"input_per_1k":0.0004,"output_per_1k":0.0016}}',
        alias="OPENAI_MODEL_PRICES_JSON",
    )

    # §5.1 interaction gating: in-app limiter (complement with API gateway in production).
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    chat_rate_limit: str = Field(default="120/minute", alias="CHAT_RATE_LIMIT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    def validate_provider_requirements(self) -> None:
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    def model_price_map(self) -> dict:
        try:
            parsed = json.loads(self.openai_model_prices_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_provider_requirements()
    return settings

