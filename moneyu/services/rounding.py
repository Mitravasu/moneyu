from __future__ import annotations

from collections.abc import Mapping, Sequence


class SplitError(ValueError):
    """Raised when expense shares are invalid."""


def calculate_even_split(
    *,
    total_cents: int,
    payer_user_id: int,
    participant_user_ids: Sequence[int],
    prior_absorptions: Mapping[int, int] | None = None,
) -> dict[int, int]:
    participants = _validate_participants(participant_user_ids)
    if total_cents <= 0:
        raise SplitError("Expense amount must be positive")

    base_share, remainder = divmod(total_cents, len(participants))
    shares = {user_id: base_share for user_id in participants}
    if remainder == 0:
        return shares

    absorption_counts = prior_absorptions or {}
    candidates = sorted(
        participants,
        key=lambda user_id: (absorption_counts.get(user_id, 0), user_id),
    )
    for user_id in candidates[:remainder]:
        shares[user_id] += 1
    return shares


def validate_custom_split(shares: Mapping[int, int]) -> dict[int, int]:
    if not shares:
        raise SplitError("Custom split must include at least one participant")
    normalized = dict(shares)
    for user_id, amount in normalized.items():
        if user_id <= 0:
            raise SplitError("Participant user IDs must be positive")
        if amount <= 0:
            raise SplitError("Custom split shares must be positive")
    return normalized


def _validate_participants(participant_user_ids: Sequence[int]) -> tuple[int, ...]:
    participants = tuple(participant_user_ids)
    if not participants:
        raise SplitError("Expense must include at least one participant")
    if len(set(participants)) != len(participants):
        raise SplitError("Expense participants must be unique")
    if any(user_id <= 0 for user_id in participants):
        raise SplitError("Participant user IDs must be positive")
    return participants
