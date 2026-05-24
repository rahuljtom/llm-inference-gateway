from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Inference Gateway"

    # Infrastructure defaults (can be overridden by .env)
    DATABASE_URL: str = "postgresql+asyncpg://gateway:gatewaypass@localhost:5432/gateway"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate as a singleton to be imported across the app
settings = Settings()
