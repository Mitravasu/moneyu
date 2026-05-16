from __future__ import annotations

import pytest

from moneyu.services.expenses import ExpenseError, validate_expense_text


def test_validate_expense_text_cleans_name_and_empty_description() -> None:
    assert validate_expense_text(name="  Fancy   Dinner ", description="  ") == (
        "Fancy Dinner",
        None,
    )


def test_validate_expense_text_keeps_description_text() -> None:
    assert validate_expense_text(name="Taxi", description=" airport ") == ("Taxi", "airport")


@pytest.mark.parametrize(
    ("name", "description"),
    [("", None), ("x" * 81, None), ("Taxi", "x" * 501)],
)
def test_validate_expense_text_rejects_invalid_values(
    name: str,
    description: str | None,
) -> None:
    with pytest.raises(ExpenseError):
        validate_expense_text(name=name, description=description)
