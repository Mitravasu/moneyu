from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SettlementEdge:
    from_user_id: int
    to_user_id: int
    amount_cents: int


def optimize_settlements(balances: Mapping[int, int]) -> list[SettlementEdge]:
    debtors = sorted(
        ((user_id, -balance) for user_id, balance in balances.items() if balance < 0),
        key=lambda item: item[0],
    )
    creditors = sorted(
        ((user_id, balance) for user_id, balance in balances.items() if balance > 0),
        key=lambda item: item[0],
    )

    settlements: list[SettlementEdge] = []
    debtor_index = 0
    creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor_id, debt = debtors[debtor_index]
        creditor_id, credit = creditors[creditor_index]
        amount = min(debt, credit)
        settlements.append(
            SettlementEdge(
                from_user_id=debtor_id,
                to_user_id=creditor_id,
                amount_cents=amount,
            )
        )

        debt -= amount
        credit -= amount
        debtors[debtor_index] = (debtor_id, debt)
        creditors[creditor_index] = (creditor_id, credit)

        if debt == 0:
            debtor_index += 1
        if credit == 0:
            creditor_index += 1

    return settlements
