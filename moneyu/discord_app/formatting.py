from __future__ import annotations

import discord

from moneyu.db.models import Expense, Payment, TripGroup, TripMember
from moneyu.services.money import format_cents
from moneyu.services.settlement import SettlementEdge

SUCCESS_COLOR = discord.Color.green()
PENDING_COLOR = discord.Color.gold()
NEUTRAL_COLOR = discord.Color.blurple()
PAGE_SIZE = 10
DISCORD_FIELD_VALUE_LIMIT = 1024
DISCORD_EMBED_TEXT_BUDGET = 5500


def user_mention(user_id: int) -> str:
    return f"<@{user_id}>"


def trip_label(group: TripGroup) -> str:
    return f"{group.name} ({group.currency})"


def trip_list_embed(groups: list[TripGroup]) -> discord.Embed:
    embed = discord.Embed(title="Trips", color=NEUTRAL_COLOR)
    if not groups:
        embed.description = "No trips have been created in this server."
        return embed
    embed.description = "\n".join(f"- {trip_label(group)}" for group in groups)
    return embed


def members_embed(group: TripGroup, members: list[TripMember]) -> discord.Embed:
    embed = discord.Embed(title=f"{group.name} members", color=NEUTRAL_COLOR)
    embed.description = (
        "\n".join(user_mention(member.user_id) for member in members) or "No members."
    )
    return embed


def status_embed(
    *,
    group: TripGroup,
    balances: dict[int, int],
    settlements: list[SettlementEdge],
    requester_user_id: int,
    private: bool,
) -> discord.Embed:
    settled = not any(balances.values())
    embed = discord.Embed(
        title=f"{group.name} status",
        color=SUCCESS_COLOR if settled else PENDING_COLOR,
    )
    if settled:
        embed.description = "Fully settled."
        return embed

    if private:
        personal = [
            edge
            for edge in settlements
            if requester_user_id in {edge.from_user_id, edge.to_user_id}
        ]
        if personal:
            embed.add_field(
                name="Your settlements",
                value="\n".join(_settlement_line(edge, group.currency) for edge in personal),
                inline=False,
            )

    embed.add_field(
        name="Balances",
        value="\n".join(
            _balance_line(user_id, cents, group.currency) for user_id, cents in balances.items()
        ),
        inline=False,
    )
    embed.add_field(
        name="Suggested settlements",
        value="\n".join(_settlement_line(edge, group.currency) for edge in settlements) or "None.",
        inline=False,
    )
    return embed


def status_embeds(
    *,
    group: TripGroup,
    balances: dict[int, int],
    settlements: list[SettlementEdge],
    requester_user_id: int,
    private: bool,
) -> list[discord.Embed]:
    settled = not any(balances.values())
    if settled:
        return [
            discord.Embed(
                title=f"{group.name} status",
                description="Fully settled.",
                color=SUCCESS_COLOR,
            )
        ]

    sections = _status_sections(
        group=group,
        balances=balances,
        settlements=settlements,
        requester_user_id=requester_user_id,
        private=private,
    )
    if _status_sections_fit_one_page(sections):
        embed = discord.Embed(title=f"{group.name} status", color=PENDING_COLOR)
        for section_name, lines in sections:
            embed.add_field(name=section_name, value="\n".join(lines), inline=False)
        return [embed]

    pages: list[discord.Embed] = []
    for section_name, lines in sections:
        for chunk in _chunks(lines, PAGE_SIZE):
            embed = discord.Embed(title=f"{group.name} status", color=PENDING_COLOR)
            embed.add_field(name=section_name, value="\n".join(chunk), inline=False)
            pages.append(embed)
    _set_page_footers(pages)
    return pages


def _status_sections(
    *,
    group: TripGroup,
    balances: dict[int, int],
    settlements: list[SettlementEdge],
    requester_user_id: int,
    private: bool,
) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    if private:
        personal = [
            edge
            for edge in settlements
            if requester_user_id in {edge.from_user_id, edge.to_user_id}
        ]
        if personal:
            sections.append(
                (
                    "Your settlements",
                    [_settlement_line(edge, group.currency) for edge in personal],
                )
            )

    sections.append(
        (
            "Balances",
            [_balance_line(user_id, cents, group.currency) for user_id, cents in balances.items()],
        )
    )
    sections.append(
        (
            "Suggested settlements",
            [_settlement_line(edge, group.currency) for edge in settlements] or ["None."],
        )
    )
    return sections


def _status_sections_fit_one_page(sections: list[tuple[str, list[str]]]) -> bool:
    total_chars = 0
    for section_name, lines in sections:
        if len(lines) > PAGE_SIZE:
            return False
        value = "\n".join(lines)
        if len(value) > DISCORD_FIELD_VALUE_LIMIT:
            return False
        total_chars += len(section_name) + len(value)
    return total_chars <= DISCORD_EMBED_TEXT_BUDGET


def expense_list_embed(group: TripGroup, expenses: list[Expense]) -> discord.Embed:
    embed = discord.Embed(title=f"{group.name} expenses", color=NEUTRAL_COLOR)
    embed.description = (
        "\n".join(_expense_summary(group, expense) for expense in expenses) or "No expenses."
    )
    return embed


def expense_list_embeds(group: TripGroup, expenses: list[Expense]) -> list[discord.Embed]:
    if not expenses:
        return [expense_list_embed(group, expenses)]
    pages = []
    for chunk in _chunks(expenses, PAGE_SIZE):
        pages.append(expense_list_embed(group, list(chunk)))
    _set_page_footers(pages)
    return pages


def expense_detail_embed(group: TripGroup, expense: Expense) -> discord.Embed:
    embed = discord.Embed(
        title=expense.name,
        description=expense.description,
        color=NEUTRAL_COLOR,
    )
    embed.add_field(name="Total", value=format_cents(expense.amount_cents, group.currency))
    embed.add_field(name="Payer", value=user_mention(expense.payer_user_id))
    embed.add_field(name="Split", value=expense.split_mode)
    embed.add_field(
        name="Shares",
        value="\n".join(
            f"{user_mention(share.user_id)}: {format_cents(share.share_cents, group.currency)}"
            for share in sorted(expense.shares, key=lambda share: share.user_id)
        ),
        inline=False,
    )
    embed.set_footer(text=f"Expense ID: {expense.id}")
    return embed


def payment_list_embed(group: TripGroup, payments: list[Payment]) -> discord.Embed:
    embed = discord.Embed(title=f"{group.name} payments", color=NEUTRAL_COLOR)
    embed.description = (
        "\n".join(_payment_summary(group, payment) for payment in payments) or "No payments."
    )
    return embed


def payment_list_embeds(group: TripGroup, payments: list[Payment]) -> list[discord.Embed]:
    if not payments:
        return [payment_list_embed(group, payments)]
    pages = []
    for chunk in _chunks(payments, PAGE_SIZE):
        pages.append(payment_list_embed(group, list(chunk)))
    _set_page_footers(pages)
    return pages


def _chunks[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _set_page_footers(pages: list[discord.Embed]) -> None:
    if len(pages) <= 1:
        return
    total = len(pages)
    for index, page in enumerate(pages, start=1):
        page.set_footer(text=f"Page {index}/{total}")


def _balance_line(user_id: int, cents: int, currency: str) -> str:
    return f"{user_mention(user_id)}: {format_cents(cents, currency)}"


def _settlement_line(edge: SettlementEdge, currency: str) -> str:
    return (
        f"{user_mention(edge.from_user_id)} pays {user_mention(edge.to_user_id)} "
        f"{format_cents(edge.amount_cents, currency)}"
    )


def _expense_summary(group: TripGroup, expense: Expense) -> str:
    return (
        f"`{expense.id}` {expense.name}: {format_cents(expense.amount_cents, group.currency)} "
        f"paid by {user_mention(expense.payer_user_id)}"
    )


def _payment_summary(group: TripGroup, payment: Payment) -> str:
    return (
        f"`{payment.id}` {user_mention(payment.from_user_id)} -> "
        f"{user_mention(payment.to_user_id)}: "
        f"{format_cents(payment.amount_cents, group.currency)}"
    )
