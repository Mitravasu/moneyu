from __future__ import annotations

import discord


class EmbedPaginator(discord.ui.View):
    def __init__(self, *, pages: list[discord.Embed], requester_user_id: int) -> None:
        super().__init__(timeout=300)
        self.pages = pages
        self.requester_user_id = requester_user_id
        self.index = 0
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_user_id:
            return True
        await interaction.response.send_message(
            "Only the command user can change pages.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[EmbedPaginator],
    ) -> None:
        _ = button
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[EmbedPaginator],
    ) -> None:
        _ = button
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    def _sync_buttons(self) -> None:
        self.previous_button.disabled = self.index == 0
        self.next_button.disabled = self.index >= len(self.pages) - 1


def paginator_for(
    *,
    pages: list[discord.Embed],
    requester_user_id: int,
) -> EmbedPaginator | None:
    if len(pages) <= 1:
        return None
    return EmbedPaginator(pages=pages, requester_user_id=requester_user_id)


async def send_paginated_embed(
    interaction: discord.Interaction,
    *,
    pages: list[discord.Embed],
    ephemeral: bool,
) -> None:
    view = paginator_for(pages=pages, requester_user_id=interaction.user.id)
    if view is None:
        await interaction.response.send_message(embed=pages[0], ephemeral=ephemeral)
        return
    await interaction.response.send_message(embed=pages[0], view=view, ephemeral=ephemeral)
