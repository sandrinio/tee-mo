"""
Application configuration for Tee-Mo backend.

Loads environment variables from the project-root .env file using Pydantic Settings.
All settings are available via the module-level ``settings`` singleton.

ADR compliance: ADR-015 (Supabase 2.28.3), ADR-017 (JWT secret >= 32 bytes).
"""

from pathlib import Path

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

    def cors_origins_list(self) -> list[str]:
        """
        Parse the comma-separated ``cors_origins`` string into a list.

        Returns
        -------
        list[str]
            Individual origin strings, stripped of whitespace, empty entries removed.
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]

# Startup validation per Roadmap ADR-017: JWT secret must be >= 32 bytes.
# Enforced at import time so the app fails fast before binding a port.
if len(settings.supabase_jwt_secret.encode("utf-8")) < 32:
    raise RuntimeError(
        "SUPABASE_JWT_SECRET must be >= 32 bytes (ADR-017). "
        f"Got {len(settings.supabase_jwt_secret.encode('utf-8'))} bytes. "
        "Generate a valid secret with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )
