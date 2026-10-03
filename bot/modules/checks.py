from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Unpack

import discord
from discord import app_commands

from .bot import bot
from .logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from discord.permissions import _PermissionsKwargs

    T = TypeVar("T")


def bot_owner_only() -> Callable[[T], T]:
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == bot.settings.owner_id

    return app_commands.check(predicate)


def server_admin_only() -> Callable[[T], T]:
    async def predicate(interaction: discord.Interaction) -> bool:
        # If interaction.user is:
        # - already a guild Member
        # - Member's guild ID matches interaction.guild.id
        # use that object
        if (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild.id == interaction.guild_id
        ):
            member = interaction.user
        else:
            # User object - try to fetch in interaction guild
            if interaction.guild is None:
                # no interaction guild + user not member - impossible to proceed
                return False
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                # exception, return false
                return False
            except Exception:  # noqa: BLE001 -- catch all other exceptions and log as error
                logger.exception(
                    "An unexpected error occurred while running "
                    "the server_admin_only permissions check. Returning non-admin "
                    "status. Traceback:",
                )
                return False

        return member.guild_permissions.administrator

    return app_commands.check(predicate)


def server_perms_check(**perms: Unpack[_PermissionsKwargs]) -> Callable[[T], T]:
    return app_commands.checks.has_permissions(**perms)


def role_check(*role_ids: int) -> Callable[[T], T]:
    async def predicate(interaction: discord.Interaction) -> bool:
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.user.guild.id != interaction.guild_id
        ):
            return False

        return any(role.id in role_ids for role in interaction.user.roles)

    return app_commands.check(predicate)
