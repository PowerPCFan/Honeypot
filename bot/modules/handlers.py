from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from .logger import logger

if TYPE_CHECKING:
    from .bot import HoneypotBot


def add_handlers(bot: HoneypotBot) -> None:
    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await bot.no_perms(interaction)
                logger.info(
                    "Command unauthorized: /%s by @%s (%s) in guild '%s' (%s)",
                    interaction.command.qualified_name if interaction.command else "<unknown>",
                    interaction.user,
                    interaction.user.id,
                    interaction.guild.name if interaction.guild else "DM",
                    interaction.guild.id if interaction.guild else "DM",
                )
        else:
            logger.error(
                "Unhandled app command error for command /%s by @%s (%s) in guild '%s' (%s):\n%s",
                interaction.command.qualified_name if interaction.command else "<unknown>",
                interaction.user,
                interaction.user.id,
                interaction.guild.name if interaction.guild else "DM",
                interaction.guild.id if interaction.guild else "DM",
                "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            )

    @bot.event
    async def on_app_command_completion(
        interaction: discord.Interaction,
        _command: app_commands.AppCommand,
    ) -> None:
        logger.info(
            "Command finished: /%s ran by @%s (%s) in guild '%s' (%s)",
            interaction.command.qualified_name if interaction.command else "<unknown>",
            interaction.user,
            interaction.user.id,
            interaction.guild.name if interaction.guild else "DM",
            interaction.guild.id if interaction.guild else "DM",
        )
