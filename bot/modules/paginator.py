from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    GetPage = Callable[[int], Awaitable[tuple[discord.Embed, int]]]


class Pagination(discord.ui.View):
    def __init__(
        self,
        interaction: discord.Interaction,
        get_page: GetPage,
        timeout_secs: float | None = 300,
    ) -> None:
        self.interaction = interaction
        self.get_page = get_page
        self.total_pages: int = 1
        self.index: int = 1
        super().__init__(timeout=timeout_secs)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True

        await interaction.response.send_message(
            embed=discord.Embed(
                description="Only the author of the command can perform this action.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        return False

    async def navigate(self) -> None:
        embed, self.total_pages = await self.get_page(self.index)
        if self.total_pages == 1:
            await self.interaction.response.send_message(embed=embed)
        elif self.total_pages > 1:
            self.update_button_states()
            await self.interaction.response.send_message(embed=embed, view=self)

    async def edit_page(self, interaction: discord.Interaction) -> None:
        emb, self.total_pages = await self.get_page(self.index)
        self.update_button_states()
        await interaction.response.edit_message(embed=emb, view=self)

    def update_button_states(self) -> None:
        on_first_page = self.index <= 1
        on_last_page = self.index >= self.total_pages
        self.first.disabled = on_first_page
        self.previous.disabled = on_first_page
        self.next.disabled = on_last_page
        self.last.disabled = on_last_page

    def disable_all_buttons(self) -> None:
        self.first.disabled = True
        self.previous.disabled = True
        self.next.disabled = True
        self.last.disabled = True

    def disable_embed(self, embed: discord.Embed) -> discord.Embed:
        name = self.interaction.command.qualified_name if self.interaction.command else "<unknown>"
        embed.color = discord.Color.greyple()
        return embed.set_footer(
            text=(
                f"{embed.footer.text + ' | ' if embed.footer.text else ''}"
                f"Timed out. Run /{name} to refresh."
            ),
        )

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.blurple)
    async def first(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[Pagination],
    ) -> None:
        self.index = 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[Pagination],
    ) -> None:
        self.index -= 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[Pagination],
    ) -> None:
        self.index += 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)
    async def last(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[Pagination],
    ) -> None:
        self.index = self.total_pages
        await self.edit_page(interaction)

    async def on_timeout(self) -> None:
        with contextlib.suppress(discord.HTTPException):
            og_msg = await self.interaction.original_response()
            self.disable_all_buttons()
            for i, e in enumerate(og_msg.embeds):
                og_msg.embeds[i] = self.disable_embed(e)
            await og_msg.edit(embeds=og_msg.embeds, view=self)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        if results_per_page <= 0:
            msg = "results_per_page must be greater than 0"
            raise ValueError(msg)

        return max(1, ((total_results - 1) // results_per_page) + 1)

