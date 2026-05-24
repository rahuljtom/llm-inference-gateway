from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    name: str
    rpm_limit: int = Field(default=60)
    tpm_limit: int = Field(default=100000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RequestLog(SQLModel, table=True):
    __tablename__ = "requests"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    api_key_id: int = Field(foreign_key="api_keys.id")
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    fallback_used: bool = Field(default=False)
    cached: bool = Field(default=False)
    cost_usd: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
