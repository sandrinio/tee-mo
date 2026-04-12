"""
Application configuration for Tee-Mo backend.

Loads environment variables from the project-root .env file using Pydantic Settings.
All settings are available via the module-level ``settings`` singleton or the
``get_settings()`` cached accessor.

ADR compliance: ADR-002 (AES-256-GCM encryption key), ADR-010 (Slack bot tokens),
ADR-015 (Supabase 2.28.3), ADR-017 (JWT secret >= 32 bytes).
"""

import base64
import binascii
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Pydantic Settings model for Tee-Mo backend configuration.

    Reads from the .env file located at the project root (three directories
    above this file: backend/app/core/ -> backend/app/ -> backend/ -> project root).

    Fields
    ------
    debug : bool
        Enables debug mode. Default False.
    cors_origins : str
        Comma-separated list of allowed CORS origins. Default "http://localhost:5173".
    supabase_url : str
        Full URL of the self-hosted Supabase instance.
    supabase_anon_key : str
        Supabase anon/public JWT key.
    supabase_service_role_key : str
        Supabase service-role key (admin privileges — never expose to client).
    supabase_jwt_secret : str
        JWT signing secret. Must be >= 32 bytes (ADR-017).
    slack_client_id : str
        Slack app client ID from the Slack app console.
    slack_client_secret : str
        Slack app client secret. NEVER log this value.
    slack_signing_secret : str
        Slack signing secret for request verification. NEVER log this value.
    slack_redirect_url : str
        OAuth redirect URL registered in the Slack app console.
    teemo_encryption_key : str
        Base64url-encoded 32-byte key for AES-256-GCM encryption (ADR-002).
        NEVER log this value — log only key_fingerprint() from encryption.py.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False
    cors_origins: str = "http://localhost:5173"
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # JWT settings — ADR-001 + Roadmap §3
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Slack integration fields — ADR-010, STORY-005A-01
    slack_client_id: str
    slack_client_secret: str
    slack_signing_secret: str
    slack_redirect_url: str

    # AES-256-GCM encryption key — ADR-002, STORY-005A-01
    # Stored as base64url string; validated to decode to exactly 32 bytes.
    teemo_encryption_key: str

    # Web search services (self-hosted) — optional, used by agent tools
    searxng_url: str = "https://searxng.soula.ge"
    crawl4ai_url: str = "https://crawler.soula.ge"

    @model_validator(mode="after")
    def _validate_encryption_key(self) -> "Settings":
        """
        Validate that teemo_encryption_key decodes to exactly 32 bytes.

        Called by Pydantic after all fields are set. Raises ValueError (wrapped
        in pydantic ValidationError) if the key is missing, not valid base64url,
        or decodes to a length other than 32 bytes (required by AES-256).

        Padding is added automatically before decoding because base64url keys
        stored in .env files typically omit trailing ``=`` padding characters.

        ADR-002: The key must be exactly 256 bits = 32 bytes.
        """
        raw_key = self.teemo_encryption_key
        # Add standard base64 padding — keys stored without trailing '=' are valid.
        padded = raw_key + "=" * (-len(raw_key) % 4)
        try:
            decoded = base64.urlsafe_b64decode(padded)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                f"TEEMO_ENCRYPTION_KEY must decode to 32 bytes (got invalid base64: {exc})"
            ) from exc

        if len(decoded) != 32:
            raise ValueError(
                f"TEEMO_ENCRYPTION_KEY must decode to 32 bytes (got {len(decoded)})"
            )
        return self

    def cors_origins_list(self) -> list[str]:
        """
        Parse the comma-separated ``cors_origins`` string into a list.

        Returns
        -------
        list[str]
            Individual origin strings, stripped of whitespace, empty entries removed.
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Uses ``functools.lru_cache`` to guarantee a single Settings instance per
    process, mirroring the ``get_supabase()`` pattern in ``app.core.db``.

    Tests can flush the cache between calls via ``get_settings.cache_clear()``
    to pick up monkeypatched environment variables.

    Returns
    -------
    Settings
        The fully-validated Settings instance.
    """
    return Settings()  # type: ignore[call-arg]


# Backward-compatible module-level singleton — existing code imports
# ``from app.core.config import settings`` directly. Keep this alias so those
# imports don't break when get_settings() is introduced (STORY-005A-01).
settings = get_settings()

# Startup validation per Roadmap ADR-017: JWT secret must be >= 32 bytes.
# Enforced at import time so the app fails fast before binding a port.
if len(settings.supabase_jwt_secret.encode("utf-8")) < 32:
    raise RuntimeError(
        "SUPABASE_JWT_SECRET must be >= 32 bytes (ADR-017). "
        f"Got {len(settings.supabase_jwt_secret.encode('utf-8'))} bytes. "
        "Generate a valid secret with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )
