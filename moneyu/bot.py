from __future__ import annotations

import asyncio
import logging

from moneyu.config import ConfigError, load_config
from moneyu.db.migrations import MigrationStateError, assert_database_current, get_alembic_config
from moneyu.db.session import create_engine, create_session_factory
from moneyu.discord_app.client import MoneyUClient
from moneyu.discord_app.context import AppContext

logger = logging.getLogger(__name__)


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("Starting MoneyU")
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration failed: %s", exc)
        raise SystemExit(f"Configuration error: {exc}") from exc

    engine = create_engine(config.database_url)
    logger.info("Checking database migration state")
    try:
        await assert_database_current(engine, get_alembic_config())
    except MigrationStateError as exc:
        logger.error("Database migration check failed: %s", exc)
        await engine.dispose()
        raise SystemExit(f"Database migration error: {exc}") from exc
    logger.info("Database migration state is current")

    logger.info(
        "Loaded MoneyU configuration for %d owner(s)%s",
        len(config.owner_user_ids),
        f" and dev guild {config.dev_guild_id}" if config.dev_guild_id else "",
    )
    client = MoneyUClient(
        AppContext(
            config=config,
            session_factory=create_session_factory(engine),
        )
    )
    try:
        logger.info("Starting Discord client")
        await client.start(config.discord_token)
    finally:
        logger.info("Shutting down database engine")
        await engine.dispose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
