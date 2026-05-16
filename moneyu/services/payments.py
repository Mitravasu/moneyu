from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyu.db.models import Payment, TripGroup
from moneyu.services.audit import snapshot_model, write_audit
from moneyu.services.ledger import group_settlements
from moneyu.services.locks import lock_trip
from moneyu.services.memberships import require_active_member
from moneyu.services.settlement import SettlementEdge


class PaymentValidationError(ValueError):
    """Raised when a payment does not match the current settlement state."""


def validate_payment_against_settlements(
    *,
    actor_user_id: int,
    from_user_id: int,
    to_user_id: int,
    amount_cents: int,
    settlements: list[SettlementEdge],
) -> None:
    if amount_cents <= 0:
        raise PaymentValidationError("Payment amount must be positive")
    if actor_user_id not in {from_user_id, to_user_id}:
        raise PaymentValidationError("Payment actor must be the sender or recipient")

    for edge in settlements:
        if edge.from_user_id == from_user_id and edge.to_user_id == to_user_id:
            if amount_cents > edge.amount_cents:
                raise PaymentValidationError("Payment amount exceeds the suggested settlement")
            return

    raise PaymentValidationError("Payment must follow a current settlement suggestion")


def validate_payment_note(note: str | None) -> str | None:
    cleaned = note.strip() if note is not None else None
    if cleaned == "":
        cleaned = None
    if cleaned is not None and len(cleaned) > 500:
        raise PaymentValidationError("Payment note must be 500 characters or fewer")
    return cleaned


async def record_payment(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    from_user_id: int,
    to_user_id: int,
    amount_cents: int,
    note: str | None = None,
) -> Payment:
    await lock_trip(session, group.id)
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)
    await require_active_member(session, group_id=group.id, user_id=from_user_id)
    await require_active_member(session, group_id=group.id, user_id=to_user_id)

    validate_payment_against_settlements(
        actor_user_id=actor_user_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount_cents=amount_cents,
        settlements=await group_settlements(session, group.id),
    )
    payment = Payment(
        group_id=group.id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount_cents=amount_cents,
        note=validate_payment_note(note),
        created_by_user_id=actor_user_id,
    )
    session.add(payment)
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="create",
        entity_type="payment",
        entity_id=payment.id,
        after=snapshot_model(payment),
    )
    return payment


async def list_payments(session: AsyncSession, *, group_id: int, limit: int = 10) -> list[Payment]:
    result = await session.scalars(
        select(Payment)
        .where(Payment.group_id == group_id, Payment.deleted_at.is_(None))
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .limit(limit)
    )
    return list(result)


async def get_payment(session: AsyncSession, *, group_id: int, payment_id: int) -> Payment | None:
    return await session.scalar(
        select(Payment).where(
            Payment.group_id == group_id,
            Payment.id == payment_id,
            Payment.deleted_at.is_(None),
        )
    )


async def delete_payment(
    session: AsyncSession,
    *,
    group: TripGroup,
    actor_user_id: int,
    payment_id: int,
) -> Payment:
    await lock_trip(session, group.id)
    payment = await get_payment(session, group_id=group.id, payment_id=payment_id)
    if payment is None:
        raise PaymentValidationError("Payment not found")
    if actor_user_id not in {payment.from_user_id, payment.to_user_id}:
        raise PaymentValidationError("Payment actor must be the sender or recipient")
    await require_active_member(session, group_id=group.id, user_id=actor_user_id)

    before = snapshot_model(payment)
    payment.deleted_at = datetime.now(UTC)
    payment.deleted_by_user_id = actor_user_id
    await session.flush()
    await write_audit(
        session,
        guild_id=group.guild_id,
        group_id=group.id,
        actor_user_id=actor_user_id,
        action="delete",
        entity_type="payment",
        entity_id=payment.id,
        before=before,
        after=snapshot_model(payment),
    )
    return payment
