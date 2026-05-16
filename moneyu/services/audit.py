from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from moneyu.db.models import AuditLog


def snapshot_model(model: object) -> dict[str, Any]:
    mapper = cast(Any, inspect(model)).mapper
    snapshot: dict[str, Any] = {}
    for column in mapper.column_attrs:
        value = getattr(model, column.key)
        if isinstance(value, datetime):
            value = value.isoformat()
        snapshot[column.key] = value
    return snapshot


async def write_audit(
    session: AsyncSession,
    *,
    guild_id: int,
    group_id: int | None,
    actor_user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    audit = AuditLog(
        guild_id=guild_id,
        group_id=group_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    session.add(audit)
    await session.flush()
    return audit
