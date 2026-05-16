from __future__ import annotations

import pytest

from moneyu.config import ConfigError, load_config


def test_load_config_parses_required_values() -> None:
    config = load_config(
        {
            "DISCORD_TOKEN": " token ",
            "DATABASE_URL": " postgresql+asyncpg://example ",
            "OWNER_USER_IDS": "123, 456,123",
            "DEV_GUILD_ID": "789",
        }
    )

    assert config.discord_token == "token"
    assert config.database_url == "postgresql+asyncpg://example"
    assert config.owner_user_ids == frozenset({123, 456})
    assert config.dev_guild_id == 789


def test_load_config_rejects_missing_required_value() -> None:
    with pytest.raises(ConfigError, match="DISCORD_TOKEN is required"):
        load_config({"DATABASE_URL": "db", "OWNER_USER_IDS": "123"})


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "123,"])
def test_load_config_rejects_invalid_owner_ids(raw: str) -> None:
    with pytest.raises(ConfigError):
        load_config({"DISCORD_TOKEN": "token", "DATABASE_URL": "db", "OWNER_USER_IDS": raw})
