from __future__ import annotations

import discord
from discord import app_commands

from moneyu.discord_app.formatting import expense_detail_embed, expense_list_embed, trip_label
from moneyu.discord_app.helpers import (
    expense_autocomplete,
    get_context,
    group_autocomplete,
    parse_int_option,
    require_group,
    run_command,
)
from moneyu.discord_app.views import (
    ExpenseFlowState,
    ExpenseParticipantView,
    build_participant_options,
)
from moneyu.services.expenses import SplitMode, delete_expense, get_expense, list_expenses
from moneyu.services.memberships import list_active_members, require_active_member

expense_group = app_commands.Group(name="expense", description="Manage expenses")


@expense_group.command(name="add", description="Add an expense")
@app_commands.autocomplete(group=group_autocomplete)
@app_commands.choices(
    split_mode=[
        app_commands.Choice(name="even", value="even"),
        app_commands.Choice(name="custom", value="custom"),
    ]
)
async def add(
    interaction: discord.Interaction,
    group: str,
    split_mode: app_commands.Choice[str],
    payer: discord.User | None = None,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        payer_id = payer.id if payer is not None else interaction.user.id
        await require_active_member(session, group_id=trip.id, user_id=interaction.user.id)
        await require_active_member(session, group_id=trip.id, user_id=payer_id)
        members = await list_active_members(session, group_id=trip.id)
        if not members:
            raise ValueError("Trip has no active members.")

        state = ExpenseFlowState(
            context=get_context(interaction),
            requester_user_id=interaction.user.id,
            group_id=trip.id,
            group_name=trip.name,
            currency=trip.currency,
            payer_user_id=payer_id,
            split_mode=SplitMode(split_mode.value),
            members=build_participant_options(guild=interaction.guild, members=members),
            selected_user_ids=tuple(member.user_id for member in members),
        )
        await interaction.response.send_message(
            _participant_message_for_command(state),
            view=ExpenseParticipantView(state),
            ephemeral=True,
        )

    await run_command(interaction, handler)


@expense_group.command(name="edit", description="Edit an expense")
@app_commands.autocomplete(group=group_autocomplete, expense=expense_autocomplete)
async def edit(interaction: discord.Interaction, group: str, expense: str) -> None:
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
        members = await list_active_members(session, group_id=trip.id)
        shares = {share.user_id: share.share_cents for share in found.shares}
        selected = tuple(
            share.user_id for share in sorted(found.shares, key=lambda share: share.user_id)
        )
        state = ExpenseFlowState(
            context=get_context(interaction),
            requester_user_id=interaction.user.id,
            group_id=trip.id,
            group_name=trip.name,
            currency=trip.currency,
            payer_user_id=found.payer_user_id,
            split_mode=SplitMode(found.split_mode),
            members=build_participant_options(guild=interaction.guild, members=members),
            selected_user_ids=selected,
            expense_id=found.id,
            default_name=found.name,
            default_description=found.description,
            default_total_cents=found.amount_cents,
            default_shares=shares,
        )
        await interaction.response.send_message(
            _participant_message_for_command(state),
            view=ExpenseParticipantView(state),
            ephemeral=True,
        )

    await run_command(interaction, handler)


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


def _participant_message_for_command(state: ExpenseFlowState) -> str:
    participants = "\n".join(f"<@{user_id}>" for user_id in state.selected_user_ids)
    action = "Edit" if state.is_edit else "Add"
    return (
        f"{action} {state.split_mode.value} expense in {state.group_name}.\n"
        f"Payer: <@{state.payer_user_id}>\n"
        f"Participants:\n{participants}"
    )


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
