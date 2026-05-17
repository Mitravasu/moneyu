from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from moneyu.db.models import Expense, ExpenseShare, TripGroup
from moneyu.services.audit import snapshot_model, write_audit
from moneyu.services.ledger import active_member_ids
from moneyu.services.locks import lock_trip
from moneyu.services.memberships import require_active_member
from moneyu.services.rounding import calculate_even_split, validate_custom_split


class ExpenseError(ValueError):
    """Raised when an expense mutation is invalid."""


class SplitMode(StrEnum):
    EVEN = "even"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class ExpenseCreate:
    name: str
    description: str | None
    payer_user_id: int
    split_mode: SplitMode
    participant_user_ids: tuple[int, ...] = ()
    total_cents: int | None = None
    custom_shares: dict[int, int] | None = None

    @classmethod
    def even(
        cls,
        *,
        name: str,
        description: str | None,
        payer_user_id: int,
        total_cents: int,
        participant_user_ids: tuple[int, ...] = (),
    ) -> Self:
        return cls(
            name=name,
            description=description,
            payer_user_id=payer_user_id,
            split_mode=SplitMode.EVEN,
            participant_user_ids=participant_user_ids,
            total_cents=total_cents,
        )

    @classmethod
    def custom(
        cls,
        *,
        name: str,
        description: str | None,
        payer_user_id: int,
        custom_shares: dict[int, int],
    ) -> Self:
        return cls(
            name=name,
            description=description,
            payer_user_id=payer_user_id,
            split_mode=SplitMode.CUSTOM,
            custom_shares=custom_shares,
        )


def validate_expense_text(*, name: str, description: str | None) -> tuple[str, str | None]:
    cleaned_name = " ".join(name.split())
    if not cleaned_name:
        raise ExpenseError("Expense name is required")
    if len(cleaned_name) > 80:
        raise ExpenseError("Expense name must be 80 characters or fewer")

    cleaned_description = description.strip() if description is not None else None
    if cleaned_description == "":
        cleaned_description = None
    if cleaned_description is not None and len(cleaned_description) > 500:
        raise ExpenseError("Expense description must be 500 characters or fewer")
    return cleaned_name, cleaned_description


async def create_expense(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    data: ExpenseCreate,
) -> Expense:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)
    await require_active_member(session, group_id=group.id, user_id=data.payer_user_id)
    name, description = validate_expense_text(name=data.name, description=data.description)
    shares = await _resolve_shares(session, group_id=group.id, data=data)

    expense = Expense(
        group_id=group.id,
        name=name,
        description=description,
        payer_user_id=data.payer_user_id,
        split_mode=data.split_mode.value,
        amount_cents=sum(shares.values()),
        created_by_user_id=actor_user_id,
    )
    expense.shares = [
        ExpenseShare(user_id=user_id, share_cents=share_cents)
        for user_id, share_cents in shares.items()
    ]
    session.add(expense)
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="create",
        entity_type="expense",
        entity_id=expense.id,
        after=_expense_snapshot(expense),
    )
    return expense


async def edit_expense(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    expense_id: int,
    data: ExpenseCreate,
) -> Expense:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)
    await require_active_member(session, group_id=group.id, user_id=data.payer_user_id)
    expense = await get_expense(session, group_id=group.id, expense_id=expense_id)
    if expense is None:
        raise ExpenseError("Expense not found")

    before = _expense_snapshot(expense)
    name, description = validate_expense_text(name=data.name, description=data.description)
    shares = await _resolve_shares(
        session,
        group_id=group.id,
        data=data,
        exclude_expense_id=expense.id,
    )

    expense.name = name
    expense.description = description
    expense.payer_user_id = data.payer_user_id
    expense.split_mode = data.split_mode.value
    expense.amount_cents = sum(shares.values())
    expense.shares = [
        ExpenseShare(user_id=user_id, share_cents=share_cents)
        for user_id, share_cents in shares.items()
    ]
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="edit",
        entity_type="expense",
        entity_id=expense.id,
        before=before,
        after=_expense_snapshot(expense),
    )
    return expense


async def list_expenses(
    session: AsyncSession,
    *,
    group_id: int,
    limit: int | None = 10,
    offset: int = 0,
) -> list[Expense]:
    statement = (
        select(Expense)
        .options(selectinload(Expense.shares))
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )
    if limit is not None:
        statement = statement.limit(limit).offset(offset)
    result = await session.scalars(statement)
    return list(result)


async def get_expense(session: AsyncSession, *, group_id: int, expense_id: int) -> Expense | None:
    return await session.scalar(
        select(Expense)
        .options(selectinload(Expense.shares))
        .where(
            Expense.group_id == group_id,
            Expense.id == expense_id,
            Expense.deleted_at.is_(None),
        )
    )


async def delete_expense(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    expense_id: int,
) -> Expense:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)
    expense = await get_expense(session, group_id=group.id, expense_id=expense_id)
    if expense is None:
        raise ExpenseError("Expense not found")

    before = _expense_snapshot(expense)
    expense.deleted_at = datetime.now(UTC)
    expense.deleted_by_user_id = actor_user_id
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="delete",
        entity_type="expense",
        entity_id=expense.id,
        before=before,
        after=_expense_snapshot(expense),
    )
    return expense


async def _resolve_shares(
    session: AsyncSession,
    *,
    group_id: int,
    data: ExpenseCreate,
    exclude_expense_id: int | None = None,
) -> dict[int, int]:
    member_ids = await active_member_ids(session, group_id)
    member_set = set(member_ids)
    if data.split_mode is SplitMode.EVEN:
        if data.total_cents is None:
            raise ExpenseError("Even split requires a total amount")
        participants = data.participant_user_ids or tuple(member_ids)
        _require_active_participants(participants, member_set)
        absorptions = await _derived_absorptions(
            session,
            group_id=group_id,
            exclude_expense_id=exclude_expense_id,
        )
        return calculate_even_split(
            total_cents=data.total_cents,
            payer_user_id=data.payer_user_id,
            participant_user_ids=participants,
            prior_absorptions=absorptions,
        )

    if data.custom_shares is None:
        raise ExpenseError("Custom split requires participant shares")
    _require_active_participants(tuple(data.custom_shares), member_set)
    return validate_custom_split(data.custom_shares)


def _require_active_participants(participants: tuple[int, ...], active_members: set[int]) -> None:
    if not participants:
        raise ExpenseError("Expense must include at least one participant")
    inactive = sorted(set(participants) - active_members)
    if inactive:
        raise ExpenseError(f"Participants are not active trip members: {inactive}")


async def _derived_absorptions(
    session: AsyncSession,
    *,
    group_id: int,
    exclude_expense_id: int | None = None,
) -> dict[int, int]:
    expenses = await session.scalars(_even_split_expenses_query(group_id, exclude_expense_id))
    absorptions: dict[int, int] = {}
    for expense in expenses:
        if not expense.shares:
            continue
        base_share = min(share.share_cents for share in expense.shares)
        for share in expense.shares:
            absorbed_cents = share.share_cents - base_share
            if absorbed_cents <= 0:
                continue
            absorptions[share.user_id] = absorptions.get(share.user_id, 0) + absorbed_cents
    return absorptions


def _even_split_expenses_query(
    group_id: int,
    exclude_expense_id: int | None = None,
) -> Select[tuple[Expense]]:
    statement = (
        select(Expense)
        .options(selectinload(Expense.shares))
        .where(
            Expense.group_id == group_id,
            Expense.deleted_at.is_(None),
            Expense.split_mode == SplitMode.EVEN.value,
        )
    )
    if exclude_expense_id is not None:
        statement = statement.where(Expense.id != exclude_expense_id)
    return statement.order_by(Expense.id)


def _expense_snapshot(expense: Expense) -> dict[str, object]:
    snapshot = snapshot_model(expense)
    snapshot["shares"] = [
        {"user_id": share.user_id, "share_cents": share.share_cents}
        for share in sorted(expense.shares, key=lambda share: share.user_id)
    ]
    return snapshot
