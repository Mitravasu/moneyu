from __future__ import annotations

import re


class TripValidationError(ValueError):
    """Raised when trip metadata is invalid."""


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_group_name(name: str) -> str:
    normalized = _WHITESPACE_RE.sub(" ", name.strip())
    if not normalized:
        raise TripValidationError("Trip group name is required")
    if len(normalized) > 80:
        raise TripValidationError("Trip group name must be 80 characters or fewer")
    return normalized.casefold()


def clean_group_name(name: str) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", name.strip())
    if not cleaned:
        raise TripValidationError("Trip group name is required")
    if len(cleaned) > 80:
        raise TripValidationError("Trip group name must be 80 characters or fewer")
    return cleaned


def normalize_currency(currency: str) -> str:
    normalized = currency.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise TripValidationError("Currency must be a 3-letter ISO 4217 code")
    return normalized
