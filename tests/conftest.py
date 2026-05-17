from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


def _to_asyncpg_dsn(url: URL) -> str:
    sync_name = "postgresql"
    async_name = "postgresql+asyncpg"
    if url.drivername == async_name:
        url = url.set(drivername=sync_name)
    return url.render_as_string(hide_password=False)


def _admin_url(url: URL) -> URL:
    return url.set(database="postgres")


@contextmanager
def _temporary_env(**values: str) -> Iterator[None]:
    original = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, previous in original.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


async def _create_database(base_url: URL, db_name: str) -> None:
    admin_conn = await asyncpg.connect(_to_asyncpg_dsn(_admin_url(base_url)))
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()


async def _drop_database(base_url: URL, db_name: str) -> None:
    admin_conn = await asyncpg.connect(_to_asyncpg_dsn(_admin_url(base_url)))
    try:
        await admin_conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            db_name,
        )
        await admin_conn.execute(f'DROP DATABASE "{db_name}"')
    finally:
        await admin_conn.close()


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    configured = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not configured:
        pytest.skip("Set TEST_DATABASE_URL (or DATABASE_URL) to run Postgres integration tests.")
    url = make_url(configured)
    if url.drivername not in {"postgresql+asyncpg", "postgresql"}:
        pytest.skip("Integration tests require a PostgreSQL database URL.")
    return configured


@pytest.fixture(scope="session")
def migrated_engine(integration_database_url: str) -> Iterator[AsyncEngine]:
    base_url = make_url(integration_database_url)
    db_name = f"moneyu_test_{uuid.uuid4().hex[:12]}"
    test_url = base_url.set(database=db_name)

    asyncio.run(_create_database(base_url, db_name))

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False))

    engine: AsyncEngine | None = None
    try:
        with _temporary_env(DATABASE_URL=test_url.render_as_string(hide_password=False)):
            command.upgrade(alembic_cfg, "head")
        engine = create_async_engine(
            test_url.render_as_string(hide_password=False),
            poolclass=NullPool,
        )
        yield engine
    finally:
        if engine is not None:
            asyncio.run(engine.dispose())
        asyncio.run(_drop_database(base_url, db_name))


@pytest.fixture
async def db_session(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with migrated_engine.connect() as connection:
        tx = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await tx.rollback()
