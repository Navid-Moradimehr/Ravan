from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )

    kafka_brokers: str = Field(
        default="localhost:19092",
        validation_alias=AliasChoices("kafka_brokers", "KAFKA_BROKERS"),
    )
    processed_topic: str = "iot.processed"
    ai_enriched_topic: str = "iot.ai_enriched"
    llm_provider: str = Field(default="openai_compat", validation_alias=AliasChoices("llm_provider", "LLM_PROVIDER"))
    llm_endpoint_url: str = Field(
        default="http://172.17.0.1:1234/v1",
        validation_alias=AliasChoices("llm_endpoint_url", "LLM_ENDPOINT_URL", "OPENAI_BASE_URL"),
    )
    llm_api_key: str = Field(
        default="lm-studio",
        validation_alias=AliasChoices("llm_api_key", "LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_model_id: str = Field(
        default="openai/gpt-oss-20B",
        validation_alias=AliasChoices("llm_model_id", "LLM_MODEL_ID", "OPENAI_MODEL"),
    )
    llm_request_path: str | None = Field(default=None, validation_alias=AliasChoices("llm_request_path", "LLM_REQUEST_PATH"))
    llm_request_format: str = Field(default="chat", validation_alias=AliasChoices("llm_request_format", "LLM_REQUEST_FORMAT"))
    llm_batch_seconds: int = 5
    llm_max_batch_size: int = 100
    llm_timeout_seconds: int = 8
    llm_allow_fallback: bool = True
    llm_local_only: bool = Field(default=False, validation_alias=AliasChoices("llm_local_only", "LLM_LOCAL_ONLY"))

    @property
    def openai_base_url(self) -> str:
        return self.llm_endpoint_url

    @property
    def openai_api_key(self) -> str:
        return self.llm_api_key

    @property
    def openai_model(self) -> str:
        return self.llm_model_id
