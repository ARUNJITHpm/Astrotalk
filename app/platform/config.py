"""App configuration — loads from env / secret manager.

Secrets are NEVER hardcoded or committed (AGENTS.md hard guardrail).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    port: int = 3000

    database_url: str = ""
    redis_url: str = ""
    chroma_host: str = ""
    chroma_port: int = 8000

    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    ephemeris_api_url: str = ""
    ephemeris_api_key: str = ""
    whatsapp_bsp_api_key: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
