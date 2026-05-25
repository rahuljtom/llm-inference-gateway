from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Inference Gateway"

    # Infrastructure defaults (can be overridden by .env)
    DATABASE_URL: str = "postgresql+asyncpg://gateway:gatewaypass@localhost:5432/gateway"
    REDIS_URL: str = "redis://localhost:6379/0"

    PROVIDER_TIMEOUT_SECONDS: float = 30.0
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    
    ADMIN_API_KEY: Optional[str] = None

    # Managed Keys
    MANAGED_OPENAI_API_KEY: Optional[str] = None
    MANAGED_ANTHROPIC_API_KEY: Optional[str] = None
    MANAGED_GROQ_API_KEY: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        """Render Postgres uses postgresql://; SQLAlchemy async needs postgresql+asyncpg://."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate as a singleton to be imported across the app
settings = Settings()
