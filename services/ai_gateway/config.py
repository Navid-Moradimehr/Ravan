from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redpanda_brokers: str = "localhost:19092"
    processed_topic: str = "iot.processed"
    ai_enriched_topic: str = "iot.ai_enriched"
    openai_base_url: str = "http://172.17.0.1:1234/v1"
    openai_api_key: str = "lm-studio"
    openai_model: str = "openai/gpt-oss-20B"
    llm_batch_seconds: int = 5
    llm_max_batch_size: int = 100
