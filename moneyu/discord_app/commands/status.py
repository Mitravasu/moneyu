from __future__ import annotations

import discord
from discord import app_commands

from moneyu.discord_app.formatting import status_embed
from moneyu.discord_app.helpers import group_autocomplete, require_group, run_command
from moneyu.services.ledger import group_balances, group_settlements
from moneyu.services.memberships import require_active_member


@app_commands.command(name="status", description="Show balances and suggested settlements")
@app_commands.autocomplete(group=group_autocomplete)
async def status_command(
    interaction: discord.Interaction,
    group: str,
    public: bool = False,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        await require_active_member(session, group_id=trip.id, user_id=interaction.user.id)
        balances = await group_balances(session, trip.id)
        settlements = await group_settlements(session, trip.id)
        await interaction.response.send_message(
            embed=status_embed(
                group=trip,
                balances=balances,
                settlements=settlements,
                requester_user_id=interaction.user.id,
                private=not public,
            ),
            ephemeral=not public,
        )

    await run_command(interaction, handler)
