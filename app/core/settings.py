from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Inference Gateway"
    
    # Provider API Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    # Infrastructure defaults (can be overridden by .env)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gateway"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate as a singleton to be imported across the app
settings = Settings()
