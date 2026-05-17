from __future__ import annotations

import pytest

from moneyu.services.trips import (
    TripValidationError,
    clean_group_name,
    normalize_currency,
    normalize_group_name,
)


def test_clean_and_normalize_group_name_collapses_whitespace() -> None:
    assert clean_group_name("  Spring   Trip 2026 ") == "Spring Trip 2026"
    assert normalize_group_name("  Spring   Trip 2026 ") == "spring trip 2026"


def test_group_name_rejects_empty_or_too_long_values() -> None:
    with pytest.raises(TripValidationError):
        clean_group_name("   ")
    with pytest.raises(TripValidationError):
        normalize_group_name("x" * 81)


def test_normalized_group_names_match_case_insensitively() -> None:
    assert normalize_group_name("Spring Trip") == normalize_group_name(" spring   trip ")


def test_normalize_currency() -> None:
    assert normalize_currency(" cad ") == "CAD"
    assert normalize_currency("usd") == "USD"


@pytest.mark.parametrize("currency", ["CA", "CADS", "12$", "", "ZZZ", "XXX", "XTS"])
def test_normalize_currency_rejects_invalid_values(currency: str) -> None:
    with pytest.raises(TripValidationError):
        normalize_currency(currency)
