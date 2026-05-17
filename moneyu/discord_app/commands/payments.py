from __future__ import annotations

import discord
from discord import app_commands

from moneyu.discord_app.formatting import payment_list_embeds, trip_label, user_mention
from moneyu.discord_app.helpers import (
    group_autocomplete,
    parse_int_option,
    payment_autocomplete,
    require_group,
    run_command,
)
from moneyu.discord_app.pagination import send_paginated_embed
from moneyu.services.memberships import require_active_member
from moneyu.services.money import format_cents, parse_amount_to_cents
from moneyu.services.payments import delete_payment, list_payments, record_payment

payment_group = app_commands.Group(name="payment", description="Record and manage payments")


@payment_group.command(name="record", description="Record a settlement payment")
@app_commands.autocomplete(group=group_autocomplete)
async def record(
    interaction: discord.Interaction,
    group: str,
    to: discord.User,
    amount: str,
    from_user: discord.User | None = None,
    note: str | None = None,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        sender_id = from_user.id if from_user is not None else interaction.user.id
        payment = await record_payment(
            session,
            group=trip,
            actor_user_id=interaction.user.id,
            from_user_id=sender_id,
            to_user_id=to.id,
            amount_cents=parse_amount_to_cents(amount),
            note=note,
        )
        await interaction.response.send_message(
            f"Recorded {user_mention(payment.from_user_id)} paying "
            f"{user_mention(payment.to_user_id)} "
            f"{format_cents(payment.amount_cents, trip.currency)} for {trip_label(trip)}."
        )

    await run_command(interaction, handler)


@payment_group.command(name="list", description="List payments")
@app_commands.autocomplete(group=group_autocomplete)
async def list_command(
    interaction: discord.Interaction,
    group: str,
    public: bool = False,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        await require_active_member(session, group_id=trip.id, user_id=interaction.user.id)
        payments = await list_payments(session, group_id=trip.id, limit=None)
        pages = payment_list_embeds(trip, payments)
        await send_paginated_embed(interaction, pages=pages, ephemeral=not public)

    await run_command(interaction, handler)


@payment_group.command(name="delete", description="Delete a payment")
@app_commands.autocomplete(group=group_autocomplete, payment=payment_autocomplete)
async def delete(
    interaction: discord.Interaction,
    group: str,
    payment: str,
) -> None:
    async def handler(session):
        trip = await require_group(session, interaction=interaction, group_name=group)
        deleted = await delete_payment(
            session,
            group=trip,
            actor_user_id=interaction.user.id,
            payment_id=parse_int_option(payment, "Payment"),
        )
        await interaction.response.send_message(
            f"Deleted payment `{deleted.id}` in {trip_label(trip)}."
        )

    await run_command(interaction, handler)
