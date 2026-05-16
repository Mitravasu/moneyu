from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord
from discord import app_commands
from sqlalchemy.ext.asyncio import AsyncSession

from moneyu.db.models import TripGroup
from moneyu.discord_app.context import AppContext
from moneyu.services.expenses import list_expenses
from moneyu.services.payments import list_payments
from moneyu.services.trips import get_trip_by_name, list_trips


class UserFacingError(ValueError):
    pass


def require_guild(interaction: discord.Interaction) -> int:
    if interaction.guild_id is None:
        raise UserFacingError("MoneyU commands can only be used in a server.")
    return interaction.guild_id


async def respond_error(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def run_command[T](
    interaction: discord.Interaction,
    handler: Callable[[AsyncSession], Awaitable[T]],
) -> T | None:
    context = get_context(interaction)
    try:
        async with context.session_factory() as session, session.begin():
            return await handler(session)
    except ValueError as exc:
        await respond_error(interaction, str(exc))
        return None


def get_context(interaction: discord.Interaction) -> AppContext:
    client = interaction.client
    context = getattr(client, "app_context", None)
    if not isinstance(context, AppContext):
        raise RuntimeError("Discord client is missing MoneyU app context")
    return context


async def require_group(
    session: AsyncSession,
    *,
    interaction: discord.Interaction,
    group_name: str,
) -> TripGroup:
    group = await get_trip_by_name(session, guild_id=require_guild(interaction), name=group_name)
    if group is None:
        raise UserFacingError("Trip group not found.")
    return group


async def group_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild_id is None:
        return []
    context = get_context(interaction)
    async with context.session_factory() as session:
        groups = await list_trips(session, guild_id=interaction.guild_id)
    current_folded = current.casefold()
    return [
        app_commands.Choice(name=group.name, value=group.name)
        for group in groups
        if current_folded in group.name.casefold()
    ][:25]


async def expense_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    group_name = getattr(interaction.namespace, "group", None)
    if interaction.guild_id is None or not isinstance(group_name, str) or not group_name:
        return []
    context = get_context(interaction)
    async with context.session_factory() as session:
        group = await get_trip_by_name(session, guild_id=interaction.guild_id, name=group_name)
        if group is None:
            return []
        expenses = await list_expenses(session, group_id=group.id, limit=25)
    current_folded = current.casefold()
    choices: list[app_commands.Choice[str]] = []
    for expense in expenses:
        label = f"{expense.id}: {expense.name}"
        if current_folded in label.casefold():
            choices.append(app_commands.Choice(name=label[:100], value=str(expense.id)))
    return choices[:25]


async def payment_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    group_name = getattr(interaction.namespace, "group", None)
    if interaction.guild_id is None or not isinstance(group_name, str) or not group_name:
        return []
    context = get_context(interaction)
    async with context.session_factory() as session:
        group = await get_trip_by_name(session, guild_id=interaction.guild_id, name=group_name)
        if group is None:
            return []
        payments = await list_payments(session, group_id=group.id, limit=25)
    current_folded = current.casefold()
    choices: list[app_commands.Choice[str]] = []
    for payment in payments:
        label = f"{payment.id}: {payment.from_user_id} -> {payment.to_user_id}"
        if current_folded in label.casefold():
            choices.append(app_commands.Choice(name=label[:100], value=str(payment.id)))
    return choices[:25]


def parse_int_option(raw: str, label: str) -> int:
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise UserFacingError(f"{label} must be selected from autocomplete.") from exc
    if value <= 0:
        raise UserFacingError(f"{label} must be selected from autocomplete.")
    return value
