from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from moneyu.db.models import Guild, TripGroup, TripMember
from moneyu.services.audit import snapshot_model, write_audit


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


async def create_trip(
    session: AsyncSession,
    *,
    guild_id: int,
    name: str,
    currency: str,
    creator_user_id: int,
) -> TripGroup:
    cleaned_name = clean_group_name(name)
    guild = await session.get(Guild, guild_id)
    if guild is None:
        session.add(Guild(id=guild_id))
        await session.flush()

    group = TripGroup(
        guild_id=guild_id,
        name=cleaned_name,
        normalized_name=normalize_group_name(cleaned_name),
        currency=normalize_currency(currency),
        created_by_user_id=creator_user_id,
    )
    session.add(group)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise TripValidationError("A trip group with that name already exists") from exc

    session.add(TripMember(group_id=group.id, user_id=creator_user_id, is_active=True))
    await session.flush()
    await write_audit(
        session,
        guild_id=guild_id,
        group_id=group.id,
        actor_user_id=creator_user_id,
        action="create",
        entity_type="trip_group",
        entity_id=group.id,
        after=snapshot_model(group),
    )
    return group


async def list_trips(session: AsyncSession, *, guild_id: int) -> list[TripGroup]:
    result = await session.scalars(
        select(TripGroup).where(TripGroup.guild_id == guild_id).order_by(TripGroup.normalized_name)
    )
    return list(result)


async def get_trip_by_name(session: AsyncSession, *, guild_id: int, name: str) -> TripGroup | None:
    return await session.scalar(
        select(TripGroup).where(
            TripGroup.guild_id == guild_id,
            TripGroup.normalized_name == normalize_group_name(name),
        )
    )
