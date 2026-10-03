from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from modules.bot import bot
from modules.checks import server_admin_only
from modules.paginator import Pagination

if TYPE_CHECKING:
    from collections.abc import Mapping

expirymap: Mapping[str, timedelta | None] = {
    "1 hour": timedelta(hours=1),
    "3 hours": timedelta(hours=3),
    "6 hours": timedelta(hours=6),
    "12 hours": timedelta(hours=12),
    "1 day": timedelta(days=1),
    "1 week": timedelta(weeks=1),
    "1 month": timedelta(days=30),
    "3 months": timedelta(days=90),
    "never": None,
}
ExpiresAtType = Literal[
    "1 hour",
    "3 hours",
    "6 hours",
    "12 hours",
    "1 day",
    "1 week",
    "1 month",
    "3 months",
    "never",
]


def convert_expires_at(expires_at: ExpiresAtType) -> datetime | None:
    delta = expirymap.get(str(expires_at.lower().strip()))
    return (datetime.now(tz=UTC) + delta) if delta else None


@server_admin_only()
@app_commands.command(
    name="add",
    description="Whitelist a user from spam detection",
)
@app_commands.describe(
    member="The user to whitelist",
    expires_in="When the whitelist should expire",
)
async def whitelist_user_command(
    interaction: discord.Interaction,
    member: discord.Member,
    expires_in: ExpiresAtType,
) -> None:
    expiry = convert_expires_at(expires_in)

    bot.whitelist.add_user(member.id, expiry)

    embed = discord.Embed(
        title="User Whitelisted",
        description="A user has been whitelisted.",
        color=discord.Color.green(),
    ).add_field(
        name="User Info",
        value="\n".join([
            f"- **Mention**: {member.mention}",
            f"- **Username**: `@{member}`",
            f"- **User ID**: `{member.id}`",
            f"- **Join Date**: {f'<t:{int(member.joined_at.timestamp())}:F>' if member.joined_at else 'Unknown'}",  # noqa: E501
            f"- **Account Created**: <t:{int(member.created_at.timestamp())}:F>",
        ]),
    )

    if expiry:
        embed.add_field(
            name="Expiry",
            value=f"<t:{int(expiry.timestamp())}:F>",
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@server_admin_only()
@app_commands.command(
    name="remove",
    description="Remove a user from the whitelist",
)
@app_commands.describe(
    member="The user to remove from the whitelist",
)
async def remove_user_from_whitelist_command(
    interaction: discord.Interaction,
    member: discord.Member,
) -> None:
    bot.whitelist.remove_user(member.id)

    await interaction.response.send_message(
        embed=discord.Embed(
            title="User Removed from Whitelist",
            description="A user has been removed from the whitelist.",
            color=discord.Color.red(),
        ).add_field(
            name="Removed User Info",
            value="\n".join([
                f"- **Mention**: {member.mention}",
                f"- **Username**: `@{member}`",
                f"- **User ID**: `{member.id}`",
                f"- **Join Date**: {f'<t:{int(member.joined_at.timestamp())}:F>' if member.joined_at else 'Unknown'}",  # noqa: E501
                f"- **Account Created**: <t:{int(member.created_at.timestamp())}:F>",
            ]),
        ),
        ephemeral=True,
    )


@server_admin_only()
@app_commands.command(
    name="view-all",
    description="View all whitelisted users",
)
async def view_whitelisted_users_command(
    interaction: discord.Interaction,
) -> None:
    users = bot.whitelist.get_all_whitelisted_users()

    if not users:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="No Whitelisted Users",
                description="There are currently no users on the whitelist.",
                color=discord.Color.yellow(),
            ),
            ephemeral=True,
        )
        return

    per_page = 10

    async def get_page(page: int) -> tuple[discord.Embed, int]:
        total_pages = Pagination.compute_total_pages(len(users), per_page)
        start = (page - 1) * per_page
        end = start + per_page

        return (
            discord.Embed(
                title="Whitelisted Users",
                description="\n".join([(
                    f"<@{user[0]}> | "
                    f"Expires {f'<t:{int(user[1].timestamp())}:R>' if user[1] else 'never'}"
                ) for user in users[start:end]]),
                color=discord.Color.green(),
            ).set_footer(
                text=f"Showing page {page}/{total_pages}",
            ),
            total_pages,
        )

    await Pagination(interaction, get_page).navigate()


@server_admin_only()
@app_commands.command(
    name="remove-expired",
    description="Remove all expired users from the whitelist",
)
async def remove_expired_whitelist_users_command(
    interaction: discord.Interaction,
) -> None:
    pre = bot.whitelist.get_all_whitelisted_users()
    bot.whitelist.remove_expired()
    post = bot.whitelist.get_all_whitelisted_users()

    removed_users = [user for user in pre if user not in post]
    diff = len(removed_users)

    if not diff:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="No Expired Users Found",
                description="There were no expired users to remove from the whitelist.",
                color=discord.Color.yellow(),
            ),
            ephemeral=True,
        )
        return

    per_page = 2
    async def get_page(page: int) -> tuple[discord.Embed, int]:
        total_pages = Pagination.compute_total_pages(len(removed_users), per_page)
        start = (page - 1) * per_page
        end = start + per_page

        return (
            discord.Embed(
                title="Expired Whitelist Users Removed",
                description=f"Removed {diff} expired users from the whitelist.",
                color=discord.Color.green(),
            ).add_field(
                name="Removed Users",
                value="\n".join([
                    f"<@{user[0]}> | Expired {f'<t:{int(user[1].timestamp())}:R>' if user[1] else 'N/A'}"  # noqa: E501
                    for user in removed_users[start:end]
                ]),
            ).set_footer(
                text=f"Showing page {page}/{total_pages}",
            ),
            total_pages,
        )

    await Pagination(interaction, get_page).navigate()
