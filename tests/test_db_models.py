from __future__ import annotations

from moneyu.db import models
from moneyu.db.base import Base


def test_metadata_contains_v1_tables() -> None:
    assert models.Guild.__tablename__ == "guilds"
    assert set(Base.metadata.tables) == {
        "audit_log",
        "expense_shares",
        "expenses",
        "guilds",
        "payments",
        "rounding_ledger",
        "trip_groups",
        "trip_members",
    }
