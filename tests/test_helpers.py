from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from moneyu.discord_app.helpers import send_celebration_message


def _interaction() -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=2),
        response=SimpleNamespace(is_done=lambda: True),
        followup=SimpleNamespace(send=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_send_celebration_message_uses_gif_content_first() -> None:
    interaction = _interaction()
    send_message = AsyncMock()

    with patch(
        "moneyu.discord_app.helpers.celebration_message",
        return_value="Base text\nhttps://example.com/gif",
    ):
        await send_celebration_message(
            interaction,
            event="expense_added",
            text="Base text",
            send_message=send_message,
            failure_notice="failed",
        )

    send_message.assert_awaited_once_with("Base text\nhttps://example.com/gif")
    interaction.followup.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_celebration_message_falls_back_to_text_only() -> None:
    interaction = _interaction()
    send_message = AsyncMock(side_effect=[RuntimeError("gif failed"), None])

    with patch(
        "moneyu.discord_app.helpers.celebration_message",
        return_value="Base text\nhttps://example.com/gif",
    ):
        await send_celebration_message(
            interaction,
            event="expense_added",
            text="Base text",
            send_message=send_message,
            failure_notice="failed",
        )

    assert send_message.await_args_list[0].args == ("Base text\nhttps://example.com/gif",)
    assert send_message.await_args_list[1].args == ("Base text",)
    interaction.followup.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_celebration_message_notifies_user_when_both_sends_fail() -> None:
    interaction = _interaction()
    send_message = AsyncMock(side_effect=RuntimeError("send failed"))

    with patch(
        "moneyu.discord_app.helpers.celebration_message",
        return_value="Base text\nhttps://example.com/gif",
    ):
        await send_celebration_message(
            interaction,
            event="payment_recorded",
            text="Base text",
            send_message=send_message,
            failure_notice="public send failed",
        )

    interaction.followup.send.assert_awaited_once_with("public send failed", ephemeral=True)
