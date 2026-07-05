"""App configuration — loads from env / secret manager.

Secrets are NEVER hardcoded or committed (AGENTS.md hard guardrail #5).

Every external integration has a ``MOCK_*`` flag that defaults to ``True`` so the
app boots and runs end-to-end with **zero** API keys. Flip a flag to ``False``
(and supply the matching credentials) to talk to the real service.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- App ----
    app_env: str = "development"
    port: int = 3000
    # Login session lifetime (bearer token TTL).
    session_ttl_hours: int = 47
    # Per-user ceiling on /chat/message calls (LLM cost / abuse protection).
    chat_rate_limit_per_hour: int = 30

    # ---- Database (PostgreSQL in prod; SQLite default in dev, see platform/db.py) ----
    # Empty = fall back to the local SQLite file so the app boots with no Postgres.
    database_url: str = ""

    # ---- Document store (MongoDB) — chat history + durable memory ----
    # Relational data (users/charts) stays in Postgres; chat logs live here.
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "tara"

    # ---- Vector DB (ChromaDB) ----
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # ---- Cache / queue (Redis + Celery) ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- LLM providers (chat replies) ----
    # Active default: "sarvam" (Malayalam-first) or "openai". A per-request
    # override may pick the other; a provider without a key falls back to the
    # other, then to the mock.
    chat_provider: str = "sarvam"
    # OpenAI
    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    # Sarvam AI — OpenAI-compatible API, Indic/Malayalam-first models.
    # sarvam-105b: strongest AND cheapest per token; sarvam-30b: lower latency.
    sarvam_api_key: str = ""
    sarvam_model: str = "sarvam-105b"
    sarvam_fast_model: str = "sarvam-30b"
    sarvam_base_url: str = "https://api.sarvam.ai/v1"
    # Embedding model for the knowledge RAG dense (vector) retriever.
    embedding_model: str = "text-embedding-ada-002"

    # ---- Ephemeris / charts ----
    # When MOCK_EPHEMERIS=false, charts are self-computed via Swiss Ephemeris
    # (no API needed). The hosted-API fields remain for an optional provider swap.
    ephemeris_api_url: str = ""
    ephemeris_api_key: str = ""
    # Sidereal mode for self-computed charts: "lahiri" | "kp" | "raman".
    ephemeris_ayanamsa: str = "lahiri"

    # ---- WhatsApp BSP (Gupshup / Wati / Twilio) + Channel ----
    whatsapp_bsp_provider: str = "gupshup"
    whatsapp_bsp_api_key: str = ""
    whatsapp_channel_id: str = ""

    # ---- Payments (Razorpay) ----
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # ---- Geocoding / timezone ----
    # Default provider is Open-Meteo's free geocoding API: no key required, and
    # it returns the IANA timezone with the coordinates (one call resolves a
    # birth place completely). The key field remains for a paid-provider swap.
    geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    geocoding_api_key: str = ""

    # ---- Mock switches: every external integration defaults to mocked ----
    # so the monolith starts and serves traffic with no third-party credentials.
    mock_openai: bool = True
    mock_ephemeris: bool = True
    mock_whatsapp: bool = True
    mock_razorpay: bool = True
    mock_geocoding: bool = True
    mock_chroma: bool = True
    # When True (default), chat history/memory persistence is skipped so the app
    # boots with no MongoDB. Set False + run mongod to enable durable chat storage.
    mock_mongo: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
