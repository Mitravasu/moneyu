from __future__ import annotations

from dataclasses import dataclass


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
