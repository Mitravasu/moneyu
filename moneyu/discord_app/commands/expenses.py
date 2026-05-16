from __future__ import annotations

import discord
from discord import app_commands

from moneyu.discord_app.formatting import expense_detail_embed, expense_list_embed, trip_label
from moneyu.discord_app.helpers import (
    expense_autocomplete,
    group_autocomplete,
    parse_int_option,
    require_group,
    run_command,
)
from moneyu.services.expenses import delete_expense, get_expense, list_expenses
from moneyu.services.memberships import require_active_member

expense_group = app_commands.Group(name="expense", description="Manage expenses")


@expense_group.command(name="list", description="List expenses")
@app_commands.autocomplete(group=group_autocomplete)
async def list_command(
    interaction: discord.Interaction,
    group: str,
    public: bool = False,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        await require_active_member(session, group_id=trip.id, user_id=interaction.user.id)
        expenses = await list_expenses(session, group_id=trip.id)
        await interaction.response.send_message(
            embed=expense_list_embed(trip, expenses),
            ephemeral=not public,
        )

    await run_command(interaction, handler)


@expense_group.command(name="show", description="Show an expense")
@app_commands.autocomplete(group=group_autocomplete, expense=expense_autocomplete)
async def show(interaction: discord.Interaction, group: str, expense: str) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        await require_active_member(session, group_id=trip.id, user_id=interaction.user.id)
        found = await get_expense(
            session,
            group_id=trip.id,
            expense_id=parse_int_option(expense, "Expense"),
        )
        if found is None:
            raise ValueError("Expense not found.")
        await interaction.response.send_message(
            embed=expense_detail_embed(trip, found), ephemeral=True
        )

    await run_command(interaction, handler)


@expense_group.command(name="delete", description="Delete an expense")
@app_commands.autocomplete(group=group_autocomplete, expense=expense_autocomplete)
async def delete(interaction: discord.Interaction, group: str, expense: str) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        deleted = await delete_expense(
            session,
            group=trip,
            actor_user_id=interaction.user.id,
            expense_id=parse_int_option(expense, "Expense"),
        )
        await interaction.response.send_message(
            f"Deleted expense `{deleted.id}` from {trip_label(trip)}."
        )

    await run_command(interaction, handler)
