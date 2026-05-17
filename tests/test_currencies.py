from __future__ import annotations

from moneyu.services.currencies import VALID_CURRENCY_CODES, currency_choices


def test_currency_choices_returns_preferred_defaults() -> None:
    choices = currency_choices("")

    assert "CAD" in {currency.code for currency in choices}
    assert "USD" in {currency.code for currency in choices}


def test_currency_choices_matches_code_and_name() -> None:
    assert [currency.code for currency in currency_choices("cad")] == ["CAD"]
    assert "JPY" in {currency.code for currency in currency_choices("yen")}


def test_currency_allowlist_contains_active_trip_currencies() -> None:
    assert {"CAD", "USD", "EUR"}.issubset(VALID_CURRENCY_CODES)
    assert "ZZZ" not in VALID_CURRENCY_CODES
