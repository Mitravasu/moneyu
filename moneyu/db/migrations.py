from __future__ import annotations

from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine


class MigrationStateError(RuntimeError):
    """Raised when the database is not at the expected migration revision."""


def get_alembic_config(config_path: str | Path = "alembic.ini") -> AlembicConfig:
    return AlembicConfig(str(config_path))


async def assert_database_current(engine: AsyncEngine, alembic_config: AlembicConfig) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    head_revision = script.get_current_head()

    async with engine.connect() as connection:
        current_revision = await connection.run_sync(
            lambda sync_connection: MigrationContext.configure(
                sync_connection
            ).get_current_revision()
        )

    if current_revision != head_revision:
        raise MigrationStateError(
            f"Database migration revision is {current_revision or 'uninitialized'}, "
            f"expected {head_revision}"
        )
