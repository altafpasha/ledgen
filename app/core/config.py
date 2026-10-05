import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "lead-intelligence-api"
    app_env: str = "development"
    # Port & Host Bindings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    postgres_port: int = 5432
    caddy_http_port: int = 8080
    caddy_https_port: int = 8443
    debug: bool = False

    # Database
    # Async database URL for FastAPI async sessions
    database_url: str = Field(
        default="sqlite+aiosqlite:///./leadgen.db",
        description="Async SQLAlchemy database URL (PostgreSQL / Supabase or SQLite)",
    )
    # Sync database URL for Celery / Alembic migrations
    database_sync_url: Optional[str] = Field(
        default=None,
        description="Synchronous database URL for Celery workers & Alembic",
    )

    # Supabase credentials (optional direct usage)
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None

    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"

    # Apify (Discovery)
    apify_api_token: Optional[str] = None
    apify_actor_id: str = "compass~crawler-google-places"

    # Apollo.io (Enrichment)
    apollo_api_key: Optional[str] = None

    # OpenRouter / Jev Model
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # Google Sheets
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_sheets_spreadsheet_id: Optional[str] = None

    # Security
    jwt_secret: str = "default-insecure-secret-key-must-be-replaced-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Initial Admin
    admin_email: str = "admin@leadgen.local"
    admin_password: str = "AdminPassword123!"

    # CORS & Frontend API Controls
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    enable_frontend_api: bool = True
    enable_api_docs: bool = True

    # Configurable Daily Scraping Targets
    default_scrape_locations: str = "KGF, Bangarapet, Bangalore"
    default_scrape_categories: str = "Dental Clinic, Healthcare Clinic, Software Company, Digital Marketing, Retail"
    default_daily_lead_limit: int = 50

    @field_validator("enable_frontend_api", "enable_api_docs", "mock_providers", mode="before")
    @classmethod
    def parse_bool_lenient(cls, v: object) -> bool:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("true", "1", "yes", "t", "y"):
                return True
            if v_clean in ("false", "fales", "0", "no", "f", "n"):
                return False
        return bool(v)

    # Concurrency & Budget Guardrails
    max_concurrent_jobs: int = 5
    max_leads_per_campaign: int = 1000
    max_apollo_credits_per_campaign: int = 100
    max_ai_requests_per_campaign: int = 500
    request_timeout_seconds: int = 30

    # Provider Mode
    mock_providers: bool = True

    @property
    def scrape_location_list(self) -> List[str]:
        if not self.default_scrape_locations:
            return ["Bangalore, India"]
        return [loc.strip() for loc in self.default_scrape_locations.split(",") if loc.strip()]

    @property
    def scrape_category_list(self) -> List[str]:
        if not self.default_scrape_categories:
            return ["Software Company", "Dental Clinic"]
        return [cat.strip() for cat in self.default_scrape_categories.split(",") if cat.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.enable_frontend_api or not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sync_database_url(self) -> str:
        if self.database_sync_url:
            return self.database_sync_url
        # If SQLite async, convert to sync sqlite
        if self.database_url.startswith("sqlite+aiosqlite:///"):
            return self.database_url.replace("sqlite+aiosqlite:///", "sqlite:///")
        # If postgres asyncpg, convert to psycopg2
        if "postgresql+asyncpg://" in self.database_url:
            return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        if self.database_url.startswith("postgresql://"):
            return self.database_url
        return self.database_url


settings = Settings()
