from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import hash_api_key
from app.core.settings import settings
from app.models.db import APIKey, Team

engine = create_async_engine(settings.DATABASE_URL, echo=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id)"
        ))
        await conn.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP WITH TIME ZONE"
        ))
        await conn.execute(text(
            "ALTER TABLE teams ADD COLUMN IF NOT EXISTS budget_monthly_usd NUMERIC(12, 6)"
        ))


async def seed_demo_api_key() -> None:
    demo_hash = hash_api_key("demo-key")
    async with AsyncSession(engine) as session:
        team_result = await session.exec(select(Team).where(Team.name == "development"))
        team = team_result.first()
        if team is None:
            team = Team(name="development")
            session.add(team)
            await session.flush()
        result = await session.exec(
            select(APIKey).where(APIKey.key_hash == demo_hash)
        )
        api_key = result.first()
        if api_key is None:
            session.add(APIKey(key_hash=demo_hash, name="demo", team_id=team.id))
        elif api_key.team_id is None:
            api_key.team_id = team.id
        await session.commit()


async def get_api_key_by_hash(key_hash: str) -> Optional[APIKey]:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.revoked_at.is_(None),
            )
        )
        return result.first()
