from __future__ import annotations

import asyncio
import logging

from moneyu.config import ConfigError, load_config
from moneyu.db.migrations import MigrationStateError, assert_database_current, get_alembic_config
from moneyu.db.session import create_engine


async def async_main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    engine = create_engine(config.database_url)
    try:
        await assert_database_current(engine, get_alembic_config())
    except MigrationStateError as exc:
        raise SystemExit(f"Database migration error: {exc}") from exc
    finally:
        await engine.dispose()

    logging.info(
        "Loaded MoneyU configuration for %d owner(s)%s",
        len(config.owner_user_ids),
        f" and dev guild {config.dev_guild_id}" if config.dev_guild_id else "",
    )
    raise SystemExit("Discord client startup is not implemented yet.")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
