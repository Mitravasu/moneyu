from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import environ


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    discord_token: str
    database_url: str
    owner_user_ids: frozenset[int]
    dev_guild_id: int | None = None


def load_config(env: Mapping[str, str] | None = None) -> Config:
    source = environ if env is None else env

    discord_token = _required(source, "DISCORD_TOKEN")
    database_url = _required(source, "DATABASE_URL")
    owner_user_ids = _parse_id_set(_required(source, "OWNER_USER_IDS"), "OWNER_USER_IDS")
    dev_guild_id = _parse_optional_id(source.get("DEV_GUILD_ID"), "DEV_GUILD_ID")

    return Config(
        discord_token=discord_token,
        database_url=database_url,
        owner_user_ids=owner_user_ids,
        dev_guild_id=dev_guild_id,
    )


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or not value.strip():
        raise ConfigError(f"{key} is required")
    return value.strip()


def _parse_id_set(raw: str, key: str) -> frozenset[int]:
    values: set[int] = set()
    for item in raw.split(","):
        stripped = item.strip()
        if not stripped:
            raise ConfigError(f"{key} must be a comma-separated list of Discord user IDs")
        values.add(_parse_positive_int(stripped, key))
    if not values:
        raise ConfigError(f"{key} must include at least one Discord user ID")
    return frozenset(values)


def _parse_optional_id(raw: str | None, key: str) -> int | None:
    if raw is None or not raw.strip():
        return None
    return _parse_positive_int(raw.strip(), key)


def _parse_positive_int(raw: str, key: str) -> int:
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise ConfigError(f"{key} must contain integer Discord IDs") from exc
    if value <= 0:
        raise ConfigError(f"{key} must contain positive Discord IDs")
    return value
