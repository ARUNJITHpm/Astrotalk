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
    # Absolute origin the app is reachable at (e.g. https://arunjith-tara.hf.space).
    # Used where a relative URL won't do: og:image on share landing pages, share
    # links that leave the platform. Empty = derived from the incoming request.
    public_base_url: str = ""
    # Referral loop (GROWTH_PLAN.md Part 2): how many referred users must
    # complete onboarding before the referrer's premium-report reward unlocks.
    referral_reward_threshold: int = 3
    # Login session lifetime (bearer token TTL).
    session_ttl_hours: int = 47
    # Per-user ceiling on /chat/message calls (LLM cost / abuse protection).
    chat_rate_limit_per_hour: int = 30
    # Shared secret gating the admin analytics dashboard (/admin). Empty in
    # development means the dashboard is open locally (dev convenience); in
    # production it MUST be set or the admin API returns 503. Sent by the page
    # as the ``X-Admin-Token`` header. Never logged.
    admin_token: str = ""

    # Shared secret gating the scheduled "cron endpoints" (e.g. POST
    # /content/run-daily), sent as ``X-Cron-Token`` by an external scheduler
    # (GitHub Actions cron / cron-job.org). Same policy as admin_token:
    # empty in dev = open locally; in production it MUST be set or the
    # endpoint returns 503. Never logged.
    cron_token: str = ""

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

    # ---- WhatsApp transport selector: which stack sends/receives 1:1 chat ----
    # "waha"  = self-hosted WAHA (GOWS/whatsmeow) — unofficial, links a real
    #           device by QR/pairing code; fragile (Meta unlinks/bans it).
    # "cloud" = official Meta WhatsApp Cloud API (graph.facebook.com) — durable,
    #           no device linking, no unlink/ban risk. Needs a Meta app + token.
    # Only the OUTBOUND adapter + which inbound webhook is authoritative change;
    # the conversation brain is identical. Default stays "waha" for back-compat.
    whatsapp_transport: str = "waha"

    # ---- Meta WhatsApp Cloud API (used when whatsapp_transport == "cloud") ----
    # From the Meta app dashboard → WhatsApp → API Setup. The access token is a
    # secret (temporary 24h token to start; swap for a permanent System User
    # token for production). Never logged, never committed.
    meta_access_token: str = ""
    # The sender's Phone Number ID (NOT the phone number itself) — a long numeric
    # id shown next to your "From" number in API Setup.
    meta_phone_number_id: str = ""
    # Graph API version to pin. Bump deliberately when Meta deprecates one.
    meta_api_version: str = "v21.0"
    # The verify token YOU invent and type into BOTH the Meta webhook config and
    # here — Meta echoes it back on the GET handshake so we can confirm the
    # webhook is ours. Any non-empty random string.
    meta_webhook_verify_token: str = ""
    # The Meta App Secret (app dashboard → Settings → Basic). When set, inbound
    # webhook POSTs are verified against the X-Hub-Signature-256 HMAC so a
    # forged caller can't inject messages. Empty = signature check skipped.
    meta_app_secret: str = ""

    # ---- WAHA (WhatsApp HTTP API) — real two-way WhatsApp chat ----
    # Base URL of the WAHA container's REST API (default: sidecar on port 3010).
    waha_api_url: str = "http://localhost:3010/api"
    # Session name configured in WAHA (matches the session started via the WAHA UI).
    waha_session: str = "default"
    # API key for WAHA (if WAHA is started with WAHA_API_KEY env var).
    waha_api_key: str = ""
    # Shared secret for verifying inbound webhook payloads (optional extra layer).
    waha_webhook_secret: str = ""
    # ---- Keep-alive: stop a scale-to-zero WAHA host (e.g. Render free tier)
    # from sleeping. Render spins the container down after ~15 min with no
    # inbound HTTP traffic; WhatsApp messages arrive over Meta's websocket (not
    # HTTP) so they don't wake it. When enabled (and not mocked), a background
    # task pings the WAHA host on an interval so it keeps seeing HTTP traffic.
    # NOTE: this only works while Tara itself is awake — if Tara is also on a
    # scale-to-zero host, pair it with an external pinger hitting Tara's /health.
    waha_keepalive_enabled: bool = False
    waha_keepalive_interval_seconds: int = 600  # 10 minutes
    # Explicit URL to ping. Empty = derive "<waha host>/ping" from waha_api_url.
    waha_keepalive_url: str = ""
    # Auto-recover a dropped WhatsApp session: each keepalive cycle, if the WAHA
    # session is FAILED/STOPPED (a transient connection drop), restart it so it
    # reconnects from the persisted creds — no human re-pair needed. Sessions in
    # SCAN_QR_CODE (a real logout needing a new QR/code) are left alone. Only
    # runs while the keepalive task is running (waha_keepalive_enabled + live).
    waha_autorecover_enabled: bool = True

    # ---- Payments (Razorpay) ----
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # Secret Razorpay signs webhook bodies with (dashboard → webhooks). With
    # mock_razorpay on and this empty, webhook signatures are skipped (dev);
    # in live mode an empty secret rejects every webhook (fail closed).
    razorpay_webhook_secret: str = ""
    # Razorpay Subscription plan ids for the white-label SaaS tiers (Part 5c).
    razorpay_plan_id_starter: str = ""
    razorpay_plan_id_pro: str = ""

    # ---- Object storage (Cloudflare R2, S3-compatible) ----
    # Generated media (share cards, report PDFs, logos) can't live on the
    # host's ephemeral disk. mock_storage=True (default) writes under
    # ``storage_dir`` on the local filesystem instead — fine for dev, and
    # files are served back via GET /media/{key}.
    storage_dir: str = "var/storage"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "tara-media"
    # Public base URL for the bucket (r2.dev subdomain or a custom domain).
    # Empty = objects are proxied through GET /media/{key} like local files.
    r2_public_base_url: str = ""

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
    # When True (default), generated media is stored on the local disk under
    # ``storage_dir``. Set False + supply the r2_* credentials for Cloudflare R2.
    mock_storage: bool = True
    # When True (default), chat history/memory persistence is skipped so the app
    # boots with no MongoDB. Set False + run mongod to enable durable chat storage.
    mock_mongo: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
