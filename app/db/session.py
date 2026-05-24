from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import hash_api_key
from app.core.settings import settings
from app.models.db import APIKey

engine = create_async_engine(settings.DATABASE_URL, echo=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_demo_api_key() -> None:
    demo_hash = hash_api_key("demo-key")
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(APIKey).where(APIKey.key_hash == demo_hash)
        )
        if result.first() is None:
            session.add(APIKey(key_hash=demo_hash, name="demo"))
            await session.commit()


async def get_api_key_by_hash(key_hash: str) -> Optional[APIKey]:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        return result.first()
