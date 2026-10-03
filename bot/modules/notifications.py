from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .logger import logger
from .models import SpamAssessment, SpamCategory

if TYPE_CHECKING:
    from .config import Settings


async def send_spam_notification(
    message: discord.Message,
    assessment: SpamAssessment,
    settings: Settings,
    *,
    actions: list[str] | None = None,
) -> None:
    if not settings.notifications.enabled:
        return

    channel = (
        message.guild.get_channel(settings.notifications.channel_id) if message.guild else None
    )
    if channel is None or not hasattr(channel, "send"):
        logger.warning(
            "Notification channel %s is unavailable or cannot send messages",
            settings.notifications.channel_id,
        )
        return

    content = (
        settings.notifications.ping
        if assessment.category in {SpamCategory.LIKELY, SpamCategory.CERTAIN}
        else None
    )

    embed = _spam_embed(message, assessment, actions)
    if not embed:
        logger.warning("Could not build spam alert embed for message %s", message.id)
        return

    allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=True)

    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        logger.warning(
            "Notification channel %s is not a text-sendable channel",
            settings.notifications.channel_id,
        )
        return

    try:
        await channel.send(content=content, embed=embed, allowed_mentions=allowed_mentions)
    except discord.HTTPException:
        logger.exception("Failed to send spam notification for message %s", message.id)
        return


async def send_honeypot_notification(
    message: discord.Message,
    settings: Settings,
    *,
    dm_sent: bool | None,
    actions: list[str] | None = None,
) -> None:
    if not settings.notifications.enabled:
        return

    channel = (
        message.guild.get_channel(settings.notifications.channel_id) if message.guild else None
    )
    if channel is None or not hasattr(channel, "send"):
        logger.warning(
            "Notification channel %s is unavailable or cannot send messages",
            settings.notifications.channel_id,
        )
        return

    if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
        logger.warning("Skipping honeypot notification for non-guild message %s", message.id)
        return

    dm_status = "Pending" if dm_sent is None else "Yes" if dm_sent else "No"

    embed = (
        discord.Embed(
            title="Honeypot Triggered",
            color=discord.Color.red(),
            description=(
                f"Member: {message.author.mention} (`{message.author.id}`)\n"
                f"Channel: {message.channel.mention}\n"
                f"DM sent: **{dm_status}**\n"
                f"Action: **{settings.honeypot.action.value}**"
            ),
        )
        .add_field(
            name="Message",
            value=_trim(message.content or "*No text content*"),
            inline=False,
        )
        .add_field(
            name="Actions Taken",
            value=("\n".join(f"- {action}" for action in (actions or []))) or "No actions taken",
        )
    )

    if isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
        logger.warning(
            "Notification channel %s is not a text-sendable channel",
            settings.notifications.channel_id,
        )
        return

    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        logger.exception("Failed to send honeypot notification for message %s", message.id)
        return


def build_staff_list(staff_role: int, guild: discord.Guild) -> str:
    staff_role_obj = guild.get_role(staff_role)
    if not staff_role_obj:
        return "*Error retrieving staff members*"

    return "\n".join([f"- {member.mention}" for member in staff_role_obj.members])


async def dm_before_action(
    member: discord.Member,
    settings: Settings,
    *,
    honeypot: bool = False,
) -> bool:
    should_dm = settings.honeypot.dm if honeypot else settings.dm_on_action
    action = settings.honeypot.action if honeypot else settings.action

    if not should_dm or (action.value != "timeout" and settings.invite_link is None):
        return False

    try:
        if action.value == "timeout":
            message = (
                f"You have been timed out in **{member.guild.name}** by the "
                "anti-spam bot. If this was a mistake, please contact "
                f"staff: {build_staff_list(settings.staff_role, member.guild)}"
            )
        elif action.value == "ban":
            message = (
                f"You have been banned from **{member.guild.name}** by the "
                "anti-spam bot. If this was a mistake, please contact "
                f"staff: {build_staff_list(settings.staff_role, member.guild)}"
                f"\nIf unbanned, you can rejoin here: {settings.invite_link}"
            )
        else:
            message = (
                f"You were kicked from **{member.guild.name}** by the anti-spam bot. "
                "If this was a mistake, you can rejoin here:\n"
                f"{settings.invite_link}"
            )

        await member.send(message)
    except discord.HTTPException:
        logger.exception("Failed to DM kick notice to member %s (%s)", member, member.id)
        return False

    return True


def _spam_embed(
    message: discord.Message,
    assessment: SpamAssessment,
    actions: list[str] | None = None,
) -> discord.Embed | None:
    if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
        return None

    color = {
        SpamCategory.POSSIBLE: discord.Color.gold(),
        SpamCategory.LIKELY: discord.Color.orange(),
        SpamCategory.CERTAIN: discord.Color.red(),
    }.get(assessment.category, discord.Color.blurple())

    embed = discord.Embed(
        title=f"Anti-Spam Alert: {assessment.category.value}",
        color=color,
        description=(
            f"Member: {message.author.mention} (`{message.author.id}`)\n"
            f"Channel: {message.channel.mention}\n"
            f"Score: **{assessment.score}**"
        ),
    )

    if assessment.certain_reason:
        embed.add_field(name="100% Spam Reason", value=assessment.certain_reason, inline=False)

    embed.add_field(
        name="Factors",
        value="\n".join(f"- {factor}" for factor in assessment.factors) or "No factors recorded",
        inline=False,
    )
    embed.add_field(
        name="Message",
        value=_trim(message.content or "*No text content*"),
        inline=False,
    )

    if actions:
        embed.add_field(
            name="Actions Taken",
            value="\n".join(f"- {action}" for action in actions),
            inline=False,
        )

    if message.attachments:
        attachment_urls = "\n".join(f"<{attachment.url}>" for attachment in message.attachments[:5])
        embed.add_field(name="Attachments", value=_trim(attachment_urls), inline=False)

    if isinstance(message.author, discord.Member):
        avatar = message.author.display_avatar
        embed.set_thumbnail(url=avatar.url)

    embed.set_footer(text=f"Message ID: {message.id}")
    return embed


def _trim(value: str, limit: int = 1024) -> str:
    if len(value) <= limit:
        return value

    return value[: limit - 3] + "..."
