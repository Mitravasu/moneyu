from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyu.db.models import Expense, ExpenseShare, Payment, TripGroup, TripMember
from moneyu.services.audit import snapshot_model, write_audit
from moneyu.services.ledger import group_balances
from moneyu.services.locks import lock_trip


class MembershipError(ValueError):
    """Raised when a membership transition is invalid."""


@dataclass(frozen=True, slots=True)
class MemberLedgerState:
    has_active_expenses: bool = False
    has_active_payments: bool = False
    balance_cents: int = 0


def can_remove_member(state: MemberLedgerState) -> None:
    if state.has_active_expenses:
        raise MembershipError("Cannot remove a member with active expenses")
    if state.has_active_payments:
        raise MembershipError("Cannot remove a member with active payments")
    if state.balance_cents != 0:
        raise MembershipError("Cannot remove a member with a nonzero balance")


def next_membership_active_state(*, existing_active: bool | None) -> bool:
    if existing_active is None:
        return True
    if existing_active:
        return True
    return True


async def require_active_member(session: AsyncSession, *, group_id: int, user_id: int) -> None:
    is_member = await session.scalar(
        select(
            exists().where(
                TripMember.group_id == group_id,
                TripMember.user_id == user_id,
                TripMember.is_active.is_(True),
            )
        )
    )
    if not is_member:
        raise MembershipError("User is not an active trip member")


async def list_active_members(session: AsyncSession, *, group_id: int) -> list[TripMember]:
    result = await session.scalars(
        select(TripMember)
        .where(TripMember.group_id == group_id, TripMember.is_active.is_(True))
        .order_by(TripMember.user_id)
    )
    return list(result)


async def add_member(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    user_id: int,
) -> TripMember:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)

    member = await session.scalar(
        select(TripMember).where(TripMember.group_id == group.id, TripMember.user_id == user_id)
    )
    before = snapshot_model(member) if member is not None else None
    if member is None:
        member = TripMember(group_id=group.id, user_id=user_id, is_active=True)
        session.add(member)
        action = "add_member"
    elif member.is_active:
        return member
    else:
        member.is_active = True
        action = "reactivate_member"

    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="trip_member",
        entity_id=member.id,
        before=before,
        after=snapshot_model(member),
    )
    return member


async def remove_member(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    user_id: int,
) -> TripMember:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)

    member = await session.scalar(
        select(TripMember).where(
            TripMember.group_id == group.id,
            TripMember.user_id == user_id,
            TripMember.is_active.is_(True),
        )
    )
    if member is None:
        raise MembershipError("User is not an active trip member")

    has_expenses = await session.scalar(
        select(
            exists().where(
                Expense.group_id == group.id,
                Expense.deleted_at.is_(None),
                or_(
                    Expense.payer_user_id == user_id,
                    Expense.shares.any(ExpenseShare.user_id == user_id),
                ),
            )
        )
    )
    has_payments = await session.scalar(
        select(
            exists().where(
                Payment.group_id == group.id,
                Payment.deleted_at.is_(None),
                or_(Payment.from_user_id == user_id, Payment.to_user_id == user_id),
            )
        )
    )
    can_remove_member(
        MemberLedgerState(
            has_active_expenses=bool(has_expenses),
            has_active_payments=bool(has_payments),
            balance_cents=(await group_balances(session, group.id)).get(user_id, 0),
        )
    )

    before = snapshot_model(member)
    member.is_active = False
    member.updated_at = datetime.now(UTC)
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="remove_member",
        entity_type="trip_member",
        entity_id=member.id,
        before=before,
        after=snapshot_model(member),
    )
    return member
