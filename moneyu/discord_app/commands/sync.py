from __future__ import annotations

from typing import Any, cast

import discord
from discord import app_commands

from moneyu.discord_app.helpers import get_context


@app_commands.command(name="sync", description="Owner-only command sync")
async def sync_command(interaction: discord.Interaction) -> None:
    context = get_context(interaction)
    if interaction.user.id not in context.config.owner_user_ids:
        await interaction.response.send_message(
            "Only bot owners can sync commands.", ephemeral=True
        )
        return

    if interaction.guild_id is not None:
        guild = discord.Object(id=interaction.guild_id)
        tree = cast(Any, interaction.client).tree
        tree.copy_global_to(guild=guild)
        synced = await tree.sync(guild=guild)
        await interaction.response.send_message(
            f"Synced {len(synced)} command(s) to this server.",
            ephemeral=True,
        )
        return

    synced = await cast(Any, interaction.client).tree.sync()
    await interaction.response.send_message(
        f"Synced {len(synced)} global command(s).", ephemeral=True
    )
