from typing import Optional
from decimal import Decimal
from sqlmodel import SQLModel, Field
from datetime import date, datetime, timezone
from sqlalchemy import Column, Date, DateTime, Numeric


class Team(SQLModel, table=True):
    __tablename__ = "teams"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=120)
    budget_monthly_usd: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(12, 6), nullable=True)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(timezone.utc),
    )

class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    name: str
    rpm_limit: int = Field(default=60)
    tpm_limit: int = Field(default=100000)
    team_id: Optional[int] = Field(default=None, foreign_key="teams.id", index=True)
    revoked_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(timezone.utc),
    )

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


class TeamBudgetUsage(SQLModel, table=True):
    __tablename__ = "team_budget_usage"

    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="teams.id", index=True)
    period_start: date = Field(sa_column=Column(Date, index=True))
    spent_usd: Decimal = Field(sa_column=Column(Numeric(16, 8), nullable=False, default=0))


class BudgetReservation(SQLModel, table=True):
    __tablename__ = "budget_reservations"

    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: str = Field(index=True, unique=True, max_length=64)
    api_key_id: int = Field(foreign_key="api_keys.id", index=True)
    team_id: int = Field(foreign_key="teams.id", index=True)
    period_start: date = Field(sa_column=Column(Date, index=True))
    reserved_usd: Decimal = Field(sa_column=Column(Numeric(16, 8), nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(timezone.utc),
    )
