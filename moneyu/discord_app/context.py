from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from moneyu.config import Config


@dataclass(frozen=True, slots=True)
class AppContext:
    config: Config
    session_factory: async_sessionmaker[AsyncSession]
