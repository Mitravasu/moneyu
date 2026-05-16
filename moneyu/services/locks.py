from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func


async def lock_trip(session: AsyncSession, group_id: int) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(group_id)))
