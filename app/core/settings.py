from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Inference Gateway"

    # Infrastructure defaults (can be overridden by .env)
    DATABASE_URL: str = "postgresql+asyncpg://gateway:gatewaypass@localhost:5432/gateway"
    REDIS_URL: str = "redis://localhost:6379/0"

    PROVIDER_TIMEOUT_SECONDS: float = 30.0
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate as a singleton to be imported across the app
settings = Settings()
