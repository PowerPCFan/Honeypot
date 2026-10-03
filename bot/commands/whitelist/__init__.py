from discord import app_commands
from discord.ext import commands

from .cmds import (
    remove_expired_whitelist_users_command,
    remove_user_from_whitelist_command,
    view_whitelisted_users_command,
    whitelist_user_command,
)


class Whitelist(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.whitelist_group = app_commands.Group(
            name="whitelist",
            description="Whitelist commands",
        )

        for cmd in [
            whitelist_user_command,
            remove_user_from_whitelist_command,
            view_whitelisted_users_command,
            remove_expired_whitelist_users_command,
        ]:
            self.whitelist_group.add_command(cmd)

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.whitelist_group)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Whitelist(bot))
