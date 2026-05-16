from __future__ import annotations

import re


class MoneyError(ValueError):
    """Raised when a money amount cannot be accepted."""


_AMOUNT_RE = re.compile(r"^(?P<dollars>\d+)(?:\.(?P<cents>\d{1,2}))?$")


def parse_amount_to_cents(raw: str) -> int:
    value = raw.strip()
    match = _AMOUNT_RE.fullmatch(value)
    if match is None:
        raise MoneyError("Amount must be positive with at most two decimal places")

    dollars = int(match.group("dollars"), 10)
    cents_raw = match.group("cents") or ""
    cents = int(cents_raw.ljust(2, "0") or "0", 10)
    total = dollars * 100 + cents
    if total <= 0:
        raise MoneyError("Amount must be greater than zero")
    return total


def format_cents(cents: int, currency: str) -> str:
    if cents < 0:
        sign = "-"
        cents = abs(cents)
    else:
        sign = ""
    return f"{sign}{currency.upper()} {cents // 100}.{cents % 100:02d}"
