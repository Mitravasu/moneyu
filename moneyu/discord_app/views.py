from __future__ import annotations

import logging
from dataclasses import dataclass

import discord
from discord import HTTPException

from moneyu.db.models import TripGroup, TripMember
from moneyu.discord_app.context import AppContext
from moneyu.discord_app.formatting import trip_label, user_mention
from moneyu.discord_app.helpers import send_celebration_message
from moneyu.services.expenses import ExpenseCreate, SplitMode, create_expense, edit_expense
from moneyu.services.money import format_cents, parse_amount_to_cents

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParticipantOption:
    user_id: int
    label: str


@dataclass(frozen=True, slots=True)
class ExpenseFlowState:
    context: AppContext
    requester_user_id: int
    group_id: int
    group_name: str
    currency: str
    payer_user_id: int
    split_mode: SplitMode
    members: tuple[ParticipantOption, ...]
    selected_user_ids: tuple[int, ...]
    expense_id: int | None = None
    default_name: str = ""
    default_description: str | None = None
    default_total_cents: int | None = None
    default_shares: dict[int, int] | None = None

    @property
    def is_edit(self) -> bool:
        return self.expense_id is not None


async def build_participant_options(
    *,
    client: discord.Client,
    guild: discord.Guild | None,
    members: list[TripMember],
) -> tuple[ParticipantOption, ...]:
    options: list[ParticipantOption] = []
    for member in members:
        label = await _participant_label(client=client, guild=guild, user_id=member.user_id)
        options.append(ParticipantOption(user_id=member.user_id, label=label[:100]))
    return tuple(options)


async def _participant_label(
    *,
    client: discord.Client,
    guild: discord.Guild | None,
    user_id: int,
) -> str:
    guild_member = guild.get_member(user_id) if guild is not None else None
    if guild_member is not None:
        return guild_member.display_name

    cached_user = client.get_user(user_id)
    if cached_user is not None:
        return cached_user.display_name

    try:
        fetched_user = await client.fetch_user(user_id)
    except discord.HTTPException:
        logger.info("Could not fetch participant user label user_id=%s", user_id)
        return str(user_id)
    return fetched_user.display_name


class ExpenseParticipantView(discord.ui.View):
    def __init__(self, state: ExpenseFlowState) -> None:
        super().__init__(timeout=300)
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.state.requester_user_id:
            return True
        await interaction.response.send_message(
            "Only the command user can use this flow.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary)
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[ExpenseParticipantView],
    ) -> None:
        _ = button
        if self.state.split_mode is SplitMode.EVEN:
            logger.info(
                "Opening even expense modal group_id=%s user_id=%s expense_id=%s",
                self.state.group_id,
                interaction.user.id,
                self.state.expense_id,
            )
            await interaction.response.send_modal(EvenExpenseModal(self.state))
            return
        logger.info(
            "Opening custom expense modal group_id=%s user_id=%s expense_id=%s",
            self.state.group_id,
            interaction.user.id,
            self.state.expense_id,
        )
        await interaction.response.send_modal(CustomExpenseModal(self.state))

    @discord.ui.button(label="Change", style=discord.ButtonStyle.secondary)
    async def change_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[ExpenseParticipantView],
    ) -> None:
        _ = button
        if len(self.state.members) > 25:
            await interaction.response.send_message(
                "Participant selection supports up to 25 active members.",
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            content=_participant_message(self.state),
            view=ParticipantSelectView(self.state),
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[ExpenseParticipantView],
    ) -> None:
        _ = button
        await interaction.response.edit_message(content="Expense flow cancelled.", view=None)


class ParticipantSelectView(discord.ui.View):
    def __init__(self, state: ExpenseFlowState) -> None:
        super().__init__(timeout=300)
        self.state = state
        self.add_item(ParticipantSelect(state))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.state.requester_user_id:
            return True
        await interaction.response.send_message(
            "Only the command user can use this flow.",
            ephemeral=True,
        )
        return False


class ParticipantSelect(discord.ui.Select[ParticipantSelectView]):
    def __init__(self, state: ExpenseFlowState) -> None:
        selected = set(state.selected_user_ids)
        options = [
            discord.SelectOption(
                label=member.label,
                value=str(member.user_id),
                default=member.user_id in selected,
            )
            for member in state.members
        ]
        super().__init__(
            placeholder="Participants",
            min_values=1,
            max_values=len(options),
            options=options,
        )
        self.state = state

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_ids = tuple(int(value) for value in self.values)
        state = _state_with_selection(self.state, selected_ids)
        logger.info(
            "Expense participants changed group_id=%s user_id=%s count=%d",
            state.group_id,
            interaction.user.id,
            len(selected_ids),
        )
        await interaction.response.edit_message(
            content=_participant_message(state),
            view=ExpenseParticipantView(state),
        )


class EvenExpenseModal(discord.ui.Modal):
    def __init__(self, state: ExpenseFlowState) -> None:
        super().__init__(title="Even expense")
        self.state = state
        self.name_input = discord.ui.TextInput(
            label="Name",
            max_length=80,
            default=state.default_name,
        )
        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            default=state.default_description,
        )
        self.amount_input = discord.ui.TextInput(
            label=f"Total amount ({state.currency})",
            default=_default_amount(state.default_total_cents, state.currency),
        )
        self.add_item(self.name_input)
        self.add_item(self.description_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            data = ExpenseCreate.even(
                name=str(self.name_input.value),
                description=str(self.description_input.value),
                payer_user_id=self.state.payer_user_id,
                total_cents=parse_amount_to_cents(str(self.amount_input.value)),
                participant_user_ids=self.state.selected_user_ids,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await _submit_expense(interaction, self.state, data)


class CustomExpenseModal(discord.ui.Modal):
    def __init__(self, state: ExpenseFlowState) -> None:
        super().__init__(title="Custom expense")
        self.state = state
        self.name_input = discord.ui.TextInput(
            label="Name",
            max_length=80,
            default=state.default_name,
        )
        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            default=state.default_description,
        )
        self.amounts_input = discord.ui.TextInput(
            label=f"Participant amounts ({state.currency})",
            style=discord.TextStyle.paragraph,
            default=_custom_amount_defaults(state),
        )
        self.add_item(self.name_input)
        self.add_item(self.description_input)
        self.add_item(self.amounts_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            shares = _parse_custom_amount_lines(self.state, str(self.amounts_input.value))
            data = ExpenseCreate.custom(
                name=str(self.name_input.value),
                description=str(self.description_input.value),
                payer_user_id=self.state.payer_user_id,
                custom_shares=shares,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await _submit_expense(interaction, self.state, data)


async def _submit_expense(
    interaction: discord.Interaction,
    state: ExpenseFlowState,
    data: ExpenseCreate,
) -> None:
    try:
        logger.info(
            "Submitting expense group_id=%s user_id=%s expense_id=%s split_mode=%s",
            state.group_id,
            state.requester_user_id,
            state.expense_id,
            data.split_mode.value,
        )
        async with state.context.session_factory() as session, session.begin():
            group = await session.get(TripGroup, state.group_id)
            if group is None:
                raise ValueError("Trip group not found.")
            if state.expense_id is None:
                expense = await create_expense(
                    session,
                    group=group,
                    actor_user_id=state.requester_user_id,
                    data=data,
                )
                verb = "Added"
            else:
                expense = await edit_expense(
                    session,
                    group=group,
                    actor_user_id=state.requester_user_id,
                    expense_id=state.expense_id,
                    data=data,
                )
                verb = "Updated"
        message = f"{verb} expense `{expense.id}` in {trip_label(group)}."
        if state.expense_id is None:
            await interaction.response.edit_message(content=message, view=None)
            await send_celebration_message(
                interaction,
                event="expense_added",
                text=message,
                send_message=_channel_sender(interaction),
                failure_notice=(
                    "The expense was saved, but I couldn't post the success message in the channel."
                ),
            )
            await _delete_expense_flow_message(interaction)
        else:
            await interaction.response.edit_message(content=message, view=None)
        logger.info(
            "Expense submitted group_id=%s user_id=%s expense_id=%s action=%s",
            state.group_id,
            state.requester_user_id,
            expense.id,
            verb.lower(),
        )
    except ValueError as exc:
        logger.info(
            "Expense submission rejected group_id=%s user_id=%s expense_id=%s error=%s",
            state.group_id,
            state.requester_user_id,
            state.expense_id,
            exc,
        )
        await interaction.response.send_message(str(exc), ephemeral=True)
    except Exception:
        logger.exception(
            "Expense submission failed group_id=%s user_id=%s expense_id=%s",
            state.group_id,
            state.requester_user_id,
            state.expense_id,
        )
        await interaction.response.send_message(
            "Something went wrong while saving that expense.",
            ephemeral=True,
        )


def _channel_sender(interaction: discord.Interaction):
    async def send(*args, **kwargs) -> None:
        channel = interaction.channel
        if channel is None:
            raise RuntimeError("Interaction channel is unavailable.")
        await channel.send(*args, **kwargs)

    return send


async def _delete_expense_flow_message(interaction: discord.Interaction) -> None:
    try:
        await interaction.delete_original_response()
    except (HTTPException, RuntimeError):
        logger.info(
            "Could not delete original expense flow response guild_id=%s user_id=%s",
            interaction.guild_id,
            interaction.user.id,
        )


def _state_with_selection(
    state: ExpenseFlowState,
    selected_user_ids: tuple[int, ...],
) -> ExpenseFlowState:
    return ExpenseFlowState(
        context=state.context,
        requester_user_id=state.requester_user_id,
        group_id=state.group_id,
        group_name=state.group_name,
        currency=state.currency,
        payer_user_id=state.payer_user_id,
        split_mode=state.split_mode,
        members=state.members,
        selected_user_ids=selected_user_ids,
        expense_id=state.expense_id,
        default_name=state.default_name,
        default_description=state.default_description,
        default_total_cents=state.default_total_cents,
        default_shares=state.default_shares,
    )


def _participant_message(state: ExpenseFlowState) -> str:
    participants = "\n".join(user_mention(user_id) for user_id in state.selected_user_ids)
    action = "Edit" if state.is_edit else "Add"
    return (
        f"{action} {state.split_mode.value} expense in {state.group_name}.\n"
        f"Payer: {user_mention(state.payer_user_id)}\n"
        f"Participants:\n{participants}"
    )


def _default_amount(cents: int | None, currency: str) -> str:
    if cents is None:
        return ""
    return format_cents(cents, currency).split(" ", 1)[1]


def _custom_amount_defaults(state: ExpenseFlowState) -> str:
    defaults = state.default_shares or {}
    lines: list[str] = []
    by_id = {member.user_id: member for member in state.members}
    for user_id in state.selected_user_ids:
        label = by_id[user_id].label if user_id in by_id else str(user_id)
        amount = _default_amount(defaults.get(user_id), state.currency)
        lines.append(f"{label}: {amount}")
    return "\n".join(lines)


def _parse_custom_amount_lines(state: ExpenseFlowState, raw: str) -> dict[int, int]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) != len(state.selected_user_ids):
        raise ValueError("Custom split must keep one amount line per selected participant.")

    shares: dict[int, int] = {}
    for user_id, line in zip(state.selected_user_ids, lines, strict=True):
        amount = line.rsplit(":", 1)[-1].strip()
        shares[user_id] = parse_amount_to_cents(amount)
    return shares
