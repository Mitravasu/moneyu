from __future__ import annotations

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
