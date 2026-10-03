from typing import Any

from discord import app_commands
from discord.ext import commands

from .cmds import (
    list_commands_command,
    load_command_command,
    reload_command_command,
    reload_config_command,
    unload_command_command,
)

discord_funcs: list[app_commands.Command[Any, Any, None]] = [
    list_commands_command,
    load_command_command,
    reload_command_command,
    reload_config_command,
    unload_command_command,
]

class Management(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Base Group
        self.base_group = app_commands.Group(
            name="management",
            description="Bot management commands",
        )

        # Subgroups
        self.cmd_group = app_commands.Group(
            name="commands",
            description="Bot command management commands",
        )
        self.settings_group = app_commands.Group(
            name="settings",
            description="Bot setting management commands",
        )

        # subgroups: groups that are added to base group + can be used w/ @command_group decorator
        self.subgroups: list[str] = ["cmd_group", "settings_group"]

        for cmd in discord_funcs:
            # try to retrieve group name from decorator, if unavailable then use base_group
            group_name: str = getattr(cmd, "command_group", "base_group")

            # retrieve group obj w/ base_group fallback, this time in case string isn't valid group
            group: app_commands.Group = getattr(self, group_name, self.base_group)

            # add command to group specified in decorator (or base group)
            group.add_command(cmd)

        # Add each subgroup to base group
        for subgroup in self.subgroups:
            self.base_group.add_command(getattr(self, subgroup))

    async def cog_load(self) -> None:
        # Add base group (with all of the subgroups added in __init__) to the bot's tree
        self.bot.tree.add_command(self.base_group)


async def setup(bot: commands.Bot) -> None:
    # Add the cog to the bot
    await bot.add_cog(Management(bot))
