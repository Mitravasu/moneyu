from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from moneyu.db.models import Expense, Payment, TripMember
from moneyu.services.balances import ExpenseLedgerEntry, PaymentLedgerEntry, compute_balances
from moneyu.services.settlement import SettlementEdge, optimize_settlements


async def active_member_ids(session: AsyncSession, group_id: int) -> list[int]:
    result = await session.scalars(
        select(TripMember.user_id)
        .where(TripMember.group_id == group_id, TripMember.is_active.is_(True))
        .order_by(TripMember.user_id)
    )
    return list(result)


async def expense_entries(session: AsyncSession, group_id: int) -> list[ExpenseLedgerEntry]:
    expenses = await session.scalars(
        select(Expense)
        .options(selectinload(Expense.shares))
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .order_by(Expense.id)
    )
    return [
        ExpenseLedgerEntry(
            payer_user_id=expense.payer_user_id,
            shares={share.user_id: share.share_cents for share in expense.shares},
        )
        for expense in expenses
    ]


async def payment_entries(session: AsyncSession, group_id: int) -> list[PaymentLedgerEntry]:
    payments = await session.scalars(
        select(Payment)
        .where(Payment.group_id == group_id, Payment.deleted_at.is_(None))
        .order_by(Payment.id)
    )
    return [
        PaymentLedgerEntry(
            from_user_id=payment.from_user_id,
            to_user_id=payment.to_user_id,
            amount_cents=payment.amount_cents,
        )
        for payment in payments
    ]


async def group_balances(session: AsyncSession, group_id: int) -> dict[int, int]:
    return compute_balances(
        member_user_ids=await active_member_ids(session, group_id),
        expenses=await expense_entries(session, group_id),
        payments=await payment_entries(session, group_id),
    )


async def group_settlements(session: AsyncSession, group_id: int) -> list[SettlementEdge]:
    return optimize_settlements(await group_balances(session, group_id))
