from __future__ import annotations

import logging

import discord
from discord import app_commands

from moneyu.discord_app.commands.expenses import expense_group
from moneyu.discord_app.commands.payments import payment_group
from moneyu.discord_app.commands.status import status_command
from moneyu.discord_app.commands.sync import sync_command
from moneyu.discord_app.commands.trips import trip_group
from moneyu.discord_app.context import AppContext

logger = logging.getLogger(__name__)


class MoneyUClient(discord.Client):
    def __init__(self, app_context: AppContext) -> None:
        super().__init__(intents=discord.Intents.default())
        self.app_context = app_context
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(trip_group)
        self.tree.add_command(expense_group)
        self.tree.add_command(payment_group)
        self.tree.add_command(status_command)
        self.tree.add_command(sync_command)

    async def setup_hook(self) -> None:
        if self.app_context.config.dev_guild_id is not None:
            guild = discord.Object(id=self.app_context.config.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Synced %d command(s) to dev guild %s",
                len(synced),
                self.app_context.config.dev_guild_id,
            )

    async def on_ready(self) -> None:
        logger.info(
            "Discord client ready user=%s guilds=%d",
            self.user,
            len(self.guilds),
        )
