from __future__ import annotations

import discord
from discord import app_commands

from moneyu.discord_app.formatting import members_embed, trip_label, trip_list_embed, user_mention
from moneyu.discord_app.helpers import group_autocomplete, require_group, require_guild, run_command
from moneyu.services.currencies import currency_choices
from moneyu.services.memberships import add_member, list_active_members, remove_member
from moneyu.services.trips import create_trip, list_trips, rename_trip

trip_group = app_commands.Group(name="trip", description="Manage trip groups")


async def currency_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    _ = interaction
    return [
        app_commands.Choice(name=currency.autocomplete_label[:100], value=currency.code)
        for currency in currency_choices(current)
    ]


@trip_group.command(name="create", description="Create a trip group")
@app_commands.describe(name="Trip name", currency="Three-letter currency code")
@app_commands.autocomplete(currency=currency_autocomplete)
async def create(interaction: discord.Interaction, name: str, currency: str) -> None:
    async def handler(session):
        group = await create_trip(
            session,
            guild_id=require_guild(interaction),
            name=name,
            currency=currency,
            creator_user_id=interaction.user.id,
        )
        await interaction.response.send_message(
            f"Created trip {trip_label(group)} with "
            f"{user_mention(interaction.user.id)} as a member."
        )

    await run_command(interaction, handler)


@trip_group.command(name="list", description="List trip groups")
async def list_command(interaction: discord.Interaction) -> None:
    async def handler(session):
        groups = await list_trips(session, guild_id=require_guild(interaction))
        await interaction.response.send_message(embed=trip_list_embed(groups))

    await run_command(interaction, handler)


@trip_group.command(name="edit", description="Rename a trip group")
@app_commands.autocomplete(group=group_autocomplete)
@app_commands.describe(group="Current trip name", name="New trip name")
async def edit(interaction: discord.Interaction, group: str, name: str) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        before = trip.name
        renamed = await rename_trip(
            session,
            group=trip,
            new_name=name,
            actor_user_id=interaction.user.id,
        )
        await interaction.response.send_message(
            f"Renamed trip `{before}` to {trip_label(renamed)}."
        )

    await run_command(interaction, handler)


@trip_group.command(name="add-member", description="Add or reactivate a trip member")
@app_commands.autocomplete(group=group_autocomplete)
async def add_member_command(
    interaction: discord.Interaction,
    group: str,
    user: discord.User,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        member = await add_member(
            session,
            group=trip,
            actor_user_id=interaction.user.id,
            user_id=user.id,
        )
        await interaction.response.send_message(
            f"Added {user_mention(member.user_id)} to {trip_label(trip)}."
        )

    await run_command(interaction, handler)


@trip_group.command(name="remove-member", description="Remove a trip member")
@app_commands.autocomplete(group=group_autocomplete)
async def remove_member_command(
    interaction: discord.Interaction,
    group: str,
    user: discord.User,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        member = await remove_member(
            session,
            group=trip,
            actor_user_id=interaction.user.id,
            user_id=user.id,
        )
        await interaction.response.send_message(
            f"Removed {user_mention(member.user_id)} from {trip_label(trip)}."
        )

    await run_command(interaction, handler)


@trip_group.command(name="members", description="List active trip members")
@app_commands.autocomplete(group=group_autocomplete)
async def members(interaction: discord.Interaction, group: str) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        active_members = await list_active_members(session, group_id=trip.id)
        await interaction.response.send_message(embed=members_embed(trip, active_members))

    await run_command(interaction, handler)
