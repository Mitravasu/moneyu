from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyu.db.models import AuditLog, Payment, TripMember
from moneyu.services.expenses import ExpenseCreate, create_expense
from moneyu.services.memberships import MembershipError, add_member, remove_member
from moneyu.services.payments import PaymentValidationError, record_payment
from moneyu.services.trips import create_trip


async def _seed_trip_with_two_members(session: AsyncSession):
    trip = await create_trip(
        session,
        guild_id=1001,
        name="Road Trip",
        currency="CAD",
        creator_user_id=101,
    )
    await add_member(session, group=trip, actor_user_id=101, user_id=202)
    return trip


async def test_create_trip_persists_membership_and_audit(db_session: AsyncSession) -> None:
    trip = await create_trip(
        db_session,
        guild_id=2002,
        name="  Montreal   Weekend  ",
        currency="cad",
        creator_user_id=303,
    )

    members = list(
        await db_session.scalars(select(TripMember).where(TripMember.group_id == trip.id))
    )
    audits = list(
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.group_id == trip.id,
                AuditLog.entity_type == "trip_group",
                AuditLog.action == "create",
            )
        )
    )

    assert trip.name == "Montreal Weekend"
    assert trip.currency == "CAD"
    assert [member.user_id for member in members] == [303]
    assert len(audits) == 1
    assert audits[0].after is not None
    assert audits[0].after["normalized_name"] == "montreal weekend"


async def test_record_payment_persists_payment_and_audit(db_session: AsyncSession) -> None:
    trip = await _seed_trip_with_two_members(db_session)
    await create_expense(
        db_session,
        group=trip,
        actor_user_id=101,
        data=ExpenseCreate.even(
            name="Dinner",
            description=None,
            payer_user_id=101,
            total_cents=1000,
            participant_user_ids=(101, 202),
        ),
    )

    payment = await record_payment(
        db_session,
        group=trip,
        actor_user_id=202,
        from_user_id=202,
        to_user_id=101,
        amount_cents=300,
        note="partial",
    )

    stored_payment = await db_session.scalar(
        select(Payment).where(Payment.group_id == trip.id, Payment.id == payment.id)
    )
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.group_id == trip.id,
            AuditLog.entity_type == "payment",
            AuditLog.entity_id == payment.id,
            AuditLog.action == "create",
        )
    )

    assert stored_payment is not None
    assert stored_payment.amount_cents == 300
    assert stored_payment.note == "partial"
    assert audit is not None
    assert audit.after is not None
    assert audit.after["from_user_id"] == 202
    assert audit.after["to_user_id"] == 101


async def test_record_payment_rejects_wrong_direction(db_session: AsyncSession) -> None:
    trip = await _seed_trip_with_two_members(db_session)
    await create_expense(
        db_session,
        group=trip,
        actor_user_id=101,
        data=ExpenseCreate.even(
            name="Hotel",
            description=None,
            payer_user_id=101,
            total_cents=1200,
            participant_user_ids=(101, 202),
        ),
    )

    try:
        await record_payment(
            db_session,
            group=trip,
            actor_user_id=101,
            from_user_id=101,
            to_user_id=202,
            amount_cents=100,
        )
    except PaymentValidationError:
        pass
    else:
        raise AssertionError("Expected PaymentValidationError for wrong payment direction")


async def test_remove_member_blocked_for_active_ledger(db_session: AsyncSession) -> None:
    trip = await _seed_trip_with_two_members(db_session)
    await create_expense(
        db_session,
        group=trip,
        actor_user_id=101,
        data=ExpenseCreate.even(
            name="Fuel",
            description=None,
            payer_user_id=101,
            total_cents=600,
            participant_user_ids=(101, 202),
        ),
    )

    try:
        await remove_member(db_session, group=trip, actor_user_id=101, user_id=202)
    except MembershipError:
        pass
    else:
        raise AssertionError("Expected MembershipError for member with active ledger involvement")
