from __future__ import annotations

import random
from typing import Literal

CelebrationEvent = Literal["expense_added", "payment_recorded"]

_GIF_POOLS: dict[CelebrationEvent, tuple[str, ...]] = {
    "expense_added": (
        "https://tenor.com/iQ4y7qpiQcN.gif",
        "https://tenor.com/vDJU.gif",
        "https://tenor.com/jKH4OieeCCl.gif",
        "https://tenor.com/5njj.gif"
    ),
    "payment_recorded": (
        "https://tenor.com/bJVwo.gif",
        "https://tenor.com/94Og.gif",
        "https://tenor.com/bk6Hg.gif",
        "https://tenor.com/bbdHe.gif",
        "https://tenor.com/bkyzQ.gif",
        "https://tenor.com/oH7m.gif",
        "https://tenor.com/q8hraOiOYFQ.gif"
    ),
}
_LAST_GIF_BY_EVENT: dict[CelebrationEvent, str] = {}


def choose_gif(event: CelebrationEvent) -> str:
    pool = _GIF_POOLS[event]
    previous = _LAST_GIF_BY_EVENT.get(event)
    candidates = tuple(url for url in pool if url != previous) or pool
    selected = random.choice(candidates)
    _LAST_GIF_BY_EVENT[event] = selected
    return selected


def celebration_message(event: CelebrationEvent, text: str) -> str:
    return f"{text}\n{choose_gif(event)}"
