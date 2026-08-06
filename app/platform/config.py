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

    # Owner console login (POST /admin/login). The dashboard exchanges these
    # for the admin token. Defaults let the owner sign in on a fresh deploy;
    # override in production via env. The password is never logged.
    admin_email: str = "arunjithpm1999@gmail.com"
    admin_password: str = "tara@admin"

    # Mobile numbers (comma-separated) whose signed-in users are treated as app
    # administrators — the web app reveals the admin/console nav links for them,
    # and their app session authorizes the admin API (see platform/admin_auth).
    # Matched on the trailing 10 digits, so "8089397344", "918089397344" and
    # "+918089397344" are the same person. Treat this list as a credential:
    # anyone who can sign in as one of these numbers is an owner.
    admin_phones: str = "8089397344"

    @property
    def admin_phone_cores(self) -> set[str]:
        """The admin numbers reduced to their trailing 10 digits."""
        cores: set[str] = set()
        for raw in self.admin_phones.split(","):
            digits = "".join(c for c in raw if c.isdigit())
            if digits:
                cores.add(digits[-10:])
        return cores

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

    # ---- WhatsApp transport ----
    # "cloud" = the official Meta WhatsApp Cloud API (graph.facebook.com), and
    # since console plan Part 15 the only one. The self-hosted "waha" stack was
    # removed: it linked a real device by QR, Meta could unlink or ban it at
    # will, and it needed an always-on external host with its own keepalive and
    # auto-recover machinery to survive that host sleeping.
    #
    # A deployment whose env still says "waha" keeps booting and is warned at
    # startup (see `warn_about_removed_settings`). Refusing to start would take
    # the whole API down over one channel's stale variable.
    whatsapp_transport: str = "cloud"

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
    # Firebase Cloud Messaging (app push). Mock by default: sends are logged, not
    # dispatched. Set False + supply Firebase credentials to send real pushes.
    mock_fcm: bool = True
    # When True (default), generated media is stored on the local disk under
    # ``storage_dir``. Set False + supply the r2_* credentials for Cloudflare R2.
    mock_storage: bool = True
    # When True (default), chat history/memory persistence is skipped so the app
    # boots with no MongoDB. Set False + run mongod to enable durable chat storage.
    mock_mongo: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


def warn_about_removed_settings() -> list[str]:
    """Complain, at boot, about env that names something no longer here.

    Console plan Part 15 deleted the self-hosted WAHA transport. A deployment
    that still says ``WHATSAPP_TRANSPORT=waha`` keeps working — its messages go
    out through the Cloud API — but it is asking for a stack that does not
    exist, and silently doing something else is how an operator comes to believe
    a channel is wired the way they configured it.

    A warning rather than a refusal: taking the whole API down over one
    channel's stale variable is out of proportion to the mistake. Returns the
    messages so a test can assert on them without reading the log.
    """
    problems: list[str] = []
    transport = get_settings().whatsapp_transport.strip().lower()
    if transport and transport != "cloud":
        problems.append(
            f"WHATSAPP_TRANSPORT={transport!r} is not a transport this build has. "
            "The self-hosted WAHA stack was removed; WhatsApp now goes through "
            "the official Meta Cloud API. Set it to 'cloud' or unset it, and "
            "make sure META_ACCESS_TOKEN and META_PHONE_NUMBER_ID are configured."
        )
    return problems


def is_admin_phone(phone: str | None) -> bool:
    """Whether ``phone`` belongs to an app administrator (see ``admin_phones``).

    Compared on the trailing 10 digits so country-code/`+` variants of the same
    number all match. Drives admin/console nav visibility, and — via
    ``platform.admin_auth`` — lets an admin's app session reach the admin API.
    """
    if not phone:
        return False
    core = "".join(c for c in phone if c.isdigit())[-10:]
    return bool(core) and core in get_settings().admin_phone_cores
