"""
Centralized application configuration.

Everything environment-specific (which origins may call the API, whether
we're in debug mode, etc.) lives here and nowhere else, so later phases
(auth secrets, database URL, LLM provider keys) have exactly one place
to be added.

Settings are read from environment variables, with optional overrides
from a local .env file (never committed — see .gitignore). See
.env.example for every variable this app currently understands.
"""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Annotated, List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger("skincare_api.config")

# Only ever used if SECRET_KEY is completely unset in development, so
# the app can still start locally. This exact string is also what the
# production check below refuses to run with — never use it for real.
_INSECURE_DEV_DEFAULT = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    # --- General ---
    app_name: str = "Smart Skin Care Assistant API"
    app_env: str = "development"  # development | staging | production
    debug: bool = True

    # --- API versioning ---
    api_v1_prefix: str = "/api/v1"

    # --- CORS ---
    # Comma-separated list in the environment, e.g.
    #   CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    # Vite's dev server defaults to port 5173 (not 3000 — that's
    # Create React App's default, and this project uses Vite).
    cors_origins: Annotated[List[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cors_allow_credentials: bool = True

    # --- Database (Phase 2) ---
    # SQLite by default for local development. The URL format is what
    # changes to move to PostgreSQL later (e.g.
    # "postgresql+psycopg://user:pass@host/dbname") — nothing else in
    # the app needs to change, since everything goes through the engine
    # built from this one value (see app/database/connection.py).
    database_url: str = "sqlite:///./skincare.db"

    # --- Authentication (Phase 3) ---
    # Set a real value in .env — this default only exists so the app
    # can start without one in development. See the production guard
    # below: the app refuses to start in production with this value.
    secret_key: str = _INSECURE_DEV_DEFAULT
    jwt_algorithm: str = "HS256"
    # 30 days, so users stay signed in between visits. Logout revokes the
    # token server-side (RevokedToken), so a long lifetime doesn't make
    # signing out meaningless.
    access_token_expire_minutes: int = 60 * 24 * 30

    # --- Google OAuth (Phase 3 prep only — not used until implemented) ---
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None

    # --- Chatbot / LLM provider (Phase 5) ---
    # Only "mock" is implemented today. The mock needs no API key and no
    # network — the backend runs and tests fully without any LLM
    # credentials. A real provider name + its key (read from the env,
    # never sent to the frontend) would be added here later.
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 20.0
    # How many prior messages of a conversation to pass to the provider
    # as context. Keeps requests bounded regardless of conversation age.
    chat_history_limit: int = 20
    # Max characters accepted in a single user chat message.
    chat_message_max_chars: int = 2000

    # --- Agent (LLM_PROVIDER=ollama) ---
    # Ollama runs the model locally, so chat data never leaves this
    # machine. Pick a model that supports tool calling (e.g. qwen2.5,
    # llama3.2). CPU inference is slow, hence the long timeout.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: float = 180.0
    # Max model<->tool round trips in one chat turn before giving up.
    agent_max_steps: int = 4
    # How long a "confirm this action" token stays valid.
    agent_action_ttl_minutes: int = 10

    # --- Cloud providers (LLM_PROVIDER=gemini or groq) ---
    # Free-tier APIs. Chat text (not face images) leaves this machine for
    # these providers — unlike "ollama", which is fully local. Left unset
    # by default; get_provider() refuses to start a cloud provider with no
    # key rather than silently falling through.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    # Groq rate-limits each model separately, so when GROQ_MODEL is busy
    # (HTTP 429) the request is retried on these, in order.
    groq_fallback_models: str = "openai/gpt-oss-20b,qwen/qwen3.8-27b"
    cloud_llm_timeout_seconds: float = 25.0
    # Comma-separated provider names tried in order, e.g. "gemini,groq".
    # A provider with no key configured is skipped, not attempted. If every
    # configured provider fails, the turn falls back to the offline mock
    # (a fixed, honestly-labelled answer) instead of erroring out, matching
    # LLM_PROVIDER=mock's existing "never pretend" contract.
    llm_fallback_chain: str | None = None

    # --- Acne model (Phase 6) ---
    # Path to a trained PyTorch checkpoint. Left empty by default
    # because no verified checkpoint exists yet — when empty (or the
    # file is missing), the acne endpoint reports "model_not_configured"
    # and never fabricates a prediction. This is NOT auto-populated by
    # any dataset; a dataset is not a trained model.
    acne_model_path: str | None = None
    # Max accepted upload size for an acne image, in megabytes.
    acne_max_image_mb: float = 8.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, value):
        """Allow CORS_ORIGINS to be given as a comma-separated string in
        the environment, while still accepting a real list (e.g. in tests
        that construct Settings directly)."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _forbid_wildcard_with_credentials(self) -> "Settings":
        """Hard safety rule from the project brief: never combine a
        wildcard CORS origin with allow_credentials=True. Browsers refuse
        this combination anyway, but we fail fast and loudly instead of
        shipping a config that silently doesn't work (or that someone
        "fixes" later by turning off credential checks instead)."""
        if "*" in self.cors_origins and self.cors_allow_credentials:
            raise ValueError(
                "Invalid configuration: CORS_ORIGINS contains '*' while "
                "cors_allow_credentials is True. Either list explicit "
                "origins, or set CORS_ALLOW_CREDENTIALS=false."
            )
        return self

    @model_validator(mode="after")
    def _refuse_insecure_production_secret(self) -> "Settings":
        """Per the project brief: "refuse insecure production
        configuration." A missing/placeholder/too-short secret key is
        fine for local development (we warn instead), but must never be
        allowed to start a production deployment."""
        insecure = self.secret_key == _INSECURE_DEV_DEFAULT or len(self.secret_key) < 32
        if insecure:
            if self.is_production:
                raise ValueError(
                    "Refusing to start: SECRET_KEY is missing, the insecure "
                    "development default, or shorter than 32 characters. Set "
                    "a real, random SECRET_KEY in the production environment."
                )
            logger.warning(
                "SECRET_KEY is not set (or is too short) — using an "
                "auto-generated key for this process only. Tokens issued "
                "now will stop working after a restart. Set SECRET_KEY in "
                ".env for stable local development, and always in production."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for the life of the process. FastAPI's
    dependency-injection system (see main.py) calls this, so tests can
    override it with app.dependency_overrides without touching real
    environment variables."""
    settings = Settings()
    # If the key is insecure and we're not in production (checked
    # above), replace it with a random per-process key so at least this
    # run of the server is using something unguessable, instead of the
    # same well-known placeholder every developer's machine would share.
    if settings.secret_key == _INSECURE_DEV_DEFAULT and not settings.is_production:
        settings = settings.model_copy(update={"secret_key": secrets.token_urlsafe(32)})
    return settings
