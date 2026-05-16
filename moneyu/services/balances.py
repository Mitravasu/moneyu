from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpenseLedgerEntry:
    payer_user_id: int
    shares: dict[int, int]

    @property
    def total_cents(self) -> int:
        return sum(self.shares.values())


@dataclass(frozen=True, slots=True)
class PaymentLedgerEntry:
    from_user_id: int
    to_user_id: int
    amount_cents: int


def compute_balances(
    *,
    member_user_ids: Iterable[int],
    expenses: Iterable[ExpenseLedgerEntry] = (),
    payments: Iterable[PaymentLedgerEntry] = (),
) -> dict[int, int]:
    balances = defaultdict(int, {user_id: 0 for user_id in member_user_ids})

    for expense in expenses:
        balances[expense.payer_user_id] += expense.total_cents
        for user_id, share_cents in expense.shares.items():
            balances[user_id] -= share_cents

    for payment in payments:
        balances[payment.from_user_id] += payment.amount_cents
        balances[payment.to_user_id] -= payment.amount_cents

    return dict(sorted(balances.items()))
