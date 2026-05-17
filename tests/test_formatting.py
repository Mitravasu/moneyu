from __future__ import annotations

from moneyu.db.models import Expense, Payment, TripGroup
from moneyu.discord_app.formatting import expense_list_embeds, payment_list_embeds, status_embeds
from moneyu.services.settlement import SettlementEdge


def test_expense_list_embeds_paginate_ten_per_page() -> None:
    group = _group()
    expenses = [
        Expense(id=index, name=f"Expense {index}", amount_cents=100, payer_user_id=1)
        for index in range(1, 12)
    ]

    pages = expense_list_embeds(group, expenses)

    assert len(pages) == 2
    assert pages[0].footer.text == "Page 1/2"
    assert pages[1].footer.text == "Page 2/2"


def test_payment_list_embeds_paginate_ten_per_page() -> None:
    group = _group()
    payments = [
        Payment(id=index, from_user_id=1, to_user_id=2, amount_cents=100) for index in range(1, 12)
    ]

    pages = payment_list_embeds(group, payments)

    assert len(pages) == 2
    assert pages[0].footer.text == "Page 1/2"
    assert pages[1].footer.text == "Page 2/2"


def test_status_embeds_paginate_large_status_sections() -> None:
    group = _group()
    balances = {index: 100 for index in range(1, 12)}
    settlements = [
        SettlementEdge(from_user_id=20 + index, to_user_id=1, amount_cents=100)
        for index in range(11)
    ]

    pages = status_embeds(
        group=group,
        balances=balances,
        settlements=settlements,
        requester_user_id=1,
        private=False,
    )

    assert len(pages) == 4
    assert pages[0].footer.text == "Page 1/4"
    assert pages[-1].footer.text == "Page 4/4"


def test_status_embeds_do_not_paginate_small_status() -> None:
    group = _group()
    balances = {1: 100, 2: -100}
    settlements = [SettlementEdge(from_user_id=2, to_user_id=1, amount_cents=100)]

    pages = status_embeds(
        group=group,
        balances=balances,
        settlements=settlements,
        requester_user_id=1,
        private=False,
    )

    assert len(pages) == 1
    assert pages[0].footer.text is None
    assert len(pages[0].fields) == 2


def _group() -> TripGroup:
    return TripGroup(id=1, guild_id=1, name="Trip", normalized_name="trip", currency="CAD")
