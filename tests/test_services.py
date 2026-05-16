from __future__ import annotations

import pytest

from moneyu.services.balances import ExpenseLedgerEntry, PaymentLedgerEntry, compute_balances
from moneyu.services.memberships import MemberLedgerState, MembershipError, can_remove_member
from moneyu.services.money import MoneyError, format_cents, parse_amount_to_cents
from moneyu.services.payments import PaymentValidationError, validate_payment_against_settlements
from moneyu.services.rounding import SplitError, calculate_even_split, validate_custom_split
from moneyu.services.settlement import SettlementEdge, optimize_settlements


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", 100), ("1.2", 120), ("1.23", 123), (" 001.05 ", 105)],
)
def test_parse_amount_to_cents(raw: str, expected: int) -> None:
    assert parse_amount_to_cents(raw) == expected


@pytest.mark.parametrize("raw", ["0", "0.00", "-1", "1.234", "1.", ".50", "abc"])
def test_parse_amount_to_cents_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(MoneyError):
        parse_amount_to_cents(raw)


def test_format_cents() -> None:
    assert format_cents(12345, "cad") == "CAD 123.45"
    assert format_cents(-501, "usd") == "-USD 5.01"


def test_even_split_without_remainder() -> None:
    assert calculate_even_split(
        total_cents=1200,
        payer_user_id=1,
        participant_user_ids=[1, 2, 3],
    ) == {1: 400, 2: 400, 3: 400}


def test_even_split_payer_absorbs_remainder_when_included() -> None:
    assert calculate_even_split(
        total_cents=1000,
        payer_user_id=2,
        participant_user_ids=[1, 2, 3],
    ) == {1: 333, 2: 334, 3: 333}


def test_even_split_uses_absorption_rotation_when_payer_excluded() -> None:
    assert calculate_even_split(
        total_cents=1000,
        payer_user_id=9,
        participant_user_ids=[3, 1, 2],
        prior_absorptions={1: 4, 2: 0, 3: 0},
    ) == {3: 333, 1: 333, 2: 334}


def test_custom_split_rejects_non_positive_shares() -> None:
    with pytest.raises(SplitError):
        validate_custom_split({1: 500, 2: 0})


def test_compute_balances_from_expenses_and_payments() -> None:
    balances = compute_balances(
        member_user_ids=[1, 2, 3],
        expenses=[
            ExpenseLedgerEntry(payer_user_id=1, shares={1: 400, 2: 400, 3: 400}),
            ExpenseLedgerEntry(payer_user_id=2, shares={1: 300, 3: 300}),
        ],
        payments=[PaymentLedgerEntry(from_user_id=3, to_user_id=1, amount_cents=200)],
    )

    assert balances == {1: 300, 2: 200, 3: -500}


def test_optimize_settlements_matches_debtors_to_creditors() -> None:
    assert optimize_settlements({1: 300, 2: 200, 3: -500}) == [
        SettlementEdge(from_user_id=3, to_user_id=1, amount_cents=300),
        SettlementEdge(from_user_id=3, to_user_id=2, amount_cents=200),
    ]


def test_payment_validation_accepts_valid_partial_payment() -> None:
    validate_payment_against_settlements(
        actor_user_id=3,
        from_user_id=3,
        to_user_id=1,
        amount_cents=200,
        settlements=[SettlementEdge(from_user_id=3, to_user_id=1, amount_cents=300)],
    )


@pytest.mark.parametrize(
    ("from_user_id", "to_user_id", "amount_cents", "actor_user_id"),
    [(3, 1, 301, 3), (1, 3, 100, 1), (3, 2, 100, 3), (3, 1, 100, 9)],
)
def test_payment_validation_rejects_invalid_payments(
    from_user_id: int,
    to_user_id: int,
    amount_cents: int,
    actor_user_id: int,
) -> None:
    with pytest.raises(PaymentValidationError):
        validate_payment_against_settlements(
            actor_user_id=actor_user_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount_cents=amount_cents,
            settlements=[SettlementEdge(from_user_id=3, to_user_id=1, amount_cents=300)],
        )


@pytest.mark.parametrize(
    "state",
    [
        MemberLedgerState(has_active_expenses=True),
        MemberLedgerState(has_active_payments=True),
        MemberLedgerState(balance_cents=1),
    ],
)
def test_member_removal_blocked_with_ledger_involvement(state: MemberLedgerState) -> None:
    with pytest.raises(MembershipError):
        can_remove_member(state)


def test_member_removal_allowed_without_ledger_involvement() -> None:
    can_remove_member(MemberLedgerState())
