from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from moneyu.config import Config
from moneyu.discord_app.client import MoneyUClient
from moneyu.discord_app.context import AppContext


def test_client_registers_expected_commands() -> None:
    client = MoneyUClient(
        AppContext(
            config=Config(
                discord_token="token",
                database_url="postgresql+asyncpg://example",
                owner_user_ids=frozenset({123}),
            ),
            session_factory=cast(async_sessionmaker[AsyncSession], object()),
        )
    )

    assert {command.name for command in client.tree.get_commands()} == {
        "expense",
        "payment",
        "status",
        "sync",
        "trip",
    }
