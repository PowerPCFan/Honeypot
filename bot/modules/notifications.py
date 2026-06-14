import discord
from modules.config import Settings
from modules.logger import logger
from modules.models import SpamAssessment, SpamCategory


async def send_spam_notification(
    message: discord.Message,
    assessment: SpamAssessment,
    settings: Settings,
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

    embed = _spam_embed(message, assessment)
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
    embed = discord.Embed(
        title="Honeypot Triggered",
        color=discord.Color.red(),
        description=(
            f"Member: {message.author.mention} (`{message.author.id}`)\n"
            f"Channel: {message.channel.mention}\n"
            f"DM sent: **{dm_status}**\n"
            f"Action: **{settings.honeypot.action.value}**"
        ),
    )
    embed.add_field(
        name="Message",
        value=_trim(message.content or "*No text content*"),
        inline=False,
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


async def dm_before_kick(
    member: discord.Member,
    settings: Settings,
    *,
    honeypot: bool = False,
) -> bool:
    should_dm = settings.honeypot.dm if honeypot else settings.dm_on_action
    if not should_dm or settings.invite_link is None:
        return False

    try:
        action = settings.honeypot.action if honeypot else settings.action
        if action.value == "timeout":
            message = (
                "The server anti-spam bot is temporarily timing out your account. "
                "If this was a mistake, please contact staff."
            )
        elif action.value == "ban":
            message = (
                "The server anti-spam bot is banning your account. "
                "If this was a mistake, please contact staff. "
                f"If staff lift the ban, you can rejoin here:\n{settings.invite_link}"
            )
        else:
            message = (
                "You were removed from the server by the anti-spam bot. "
                "If this was a mistake, you can rejoin here:\n"
                f"{settings.invite_link}"
            )

        await member.send(message)
    except discord.HTTPException:
        logger.exception("Failed to DM kick notice to member %s (%s)", member, member.id)
        return False

    return True


def _spam_embed(message: discord.Message, assessment: SpamAssessment) -> discord.Embed | None:
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

    if message.attachments:
        attachment_urls = "\n".join(attachment.url for attachment in message.attachments[:5])
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
