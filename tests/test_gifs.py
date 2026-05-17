from __future__ import annotations

from unittest.mock import patch

from moneyu.discord_app import gifs


def setup_function() -> None:
    gifs._LAST_GIF_BY_EVENT.clear()


def test_choose_gif_avoids_immediate_repeat() -> None:
    previous = gifs._GIF_POOLS["expense_added"][0]
    gifs._LAST_GIF_BY_EVENT["expense_added"] = previous

    with patch("moneyu.discord_app.gifs.random.choice", side_effect=lambda seq: seq[0]):
        selected = gifs.choose_gif("expense_added")

    assert selected != previous


def test_celebration_message_appends_gif_url() -> None:
    with patch("moneyu.discord_app.gifs.choose_gif", return_value="https://example.com/gif"):
        message = gifs.celebration_message("payment_recorded", "Recorded payment.")

    assert message == "Recorded payment.\nhttps://example.com/gif"
