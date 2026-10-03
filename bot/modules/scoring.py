from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import discord

from .logger import logger
from .models import SpamAssessment, SpamCategory

if TYPE_CHECKING:
    from .config import Settings
    from .state import MessageMemory

DISCORD_CDN_RE = re.compile(
    r"https?://(?:(?:cdn|media)\.discordapp\.(?:com|net)|images-ext-\d+\.discordapp\.net)/attachments/\S+",
    re.IGNORECASE,
)

SUSPICIOUS_PROFILE_KEYWORDS = (
    "free",
    "nitro",
    "discord",
    "gift",
    "steam",
    "steamgifts",
    "giveaway",
    "giveaways",
)


def assess_message(  # noqa: C901
    message: discord.Message,
    memory: MessageMemory,
    settings: Settings,
) -> SpamAssessment:
    if not isinstance(message.author, discord.Member):
        return SpamAssessment(category=SpamCategory.NONE, score=0)

    member = message.author
    score = 0
    factors: list[str] = []

    cdn_link_count = len(DISCORD_CDN_RE.findall(message.content))
    attachment_count = len(message.attachments)
    repeated_channel_count = memory.record_and_count_channels(
        member.id,
        message.content,
        message.channel.id,
    )

    if cdn_link_count >= 2:  # noqa: PLR2004
        score += 4
        factors.append(f"{cdn_link_count} Discord CDN links")
    elif cdn_link_count == 1:
        score += 1
        factors.append("1 Discord CDN link")

    if attachment_count >= 2:  # noqa: PLR2004
        score += 2
        factors.append(f"{attachment_count} attachments")

    if repeated_channel_count >= 2:  # noqa: PLR2004
        score += 4
        factors.append(f"Same message sent in {repeated_channel_count} channels (within 60 seconds)")  # noqa: E501

    profile_score, profile_factors = assess_profile(member)
    logger.debug(
        "Profile assessment for @%s: +%d points\nFactors:\n- %s",
        member,
        profile_score,
        "\n- ".join(profile_factors) if profile_factors else "None",
    )
    score += profile_score
    factors.extend(profile_factors)

    clean_message_count = memory.clean_count_for(member.id)
    if clean_message_count >= 20:  # noqa: PLR2004
        score -= 3
        factors.append("Established local message history (-3)")
    elif clean_message_count >= 5:  # noqa: PLR2004
        score -= 1
        factors.append("Some local message history (-1)")

    score = max(score, 0)

    certain_reason = _certain_reason(
        score=score,
        settings=settings,
        cdn_link_count=cdn_link_count,
        attachment_count=attachment_count,
        repeated_channel_count=repeated_channel_count,
    )

    if certain_reason is not None:
        return SpamAssessment(
            category=SpamCategory.CERTAIN,
            score=score,
            factors=factors,
            certain_reason=certain_reason,
        )

    if score >= settings.thresholds.likely:
        return SpamAssessment(category=SpamCategory.LIKELY, score=score, factors=factors)

    if score >= settings.thresholds.possible:
        return SpamAssessment(category=SpamCategory.POSSIBLE, score=score, factors=factors)

    return SpamAssessment(category=SpamCategory.NONE, score=score, factors=factors)


def assess_profile(member: discord.Member) -> tuple[int, list[str]]:
    score = 0
    factors: list[str] = []
    username = member.name.casefold()
    nickname = member.display_name.casefold()

    one_month_ago = datetime.now(tz=UTC) - timedelta(days=30)
    if member.created_at > one_month_ago:
        score += 1
        factors.append("Account younger than 30 days")

    if member.avatar is None:
        score += 1
        factors.append("Default profile picture")

    web_status = getattr(member, "web_status", None)
    if web_status is not None and web_status is not discord.Status.offline:
        score += 1
        factors.append("Using web client")

    if any(keyword in nickname or keyword in username for keyword in SUSPICIOUS_PROFILE_KEYWORDS):
        score += 2
        factors.append("Suspicious keyword in username/nickname")

    return score, factors


def _certain_reason(
    score: int,
    settings: Settings,
    cdn_link_count: int,
    attachment_count: int,
    repeated_channel_count: int,
) -> str | None:
    if score >= settings.thresholds.certain:
        return "Score met 100% spam threshold"

    if repeated_channel_count >= 2 and cdn_link_count >= 2:  # noqa: PLR2004
        return "Same message repeated across channels with multiple Discord CDN links"

    if repeated_channel_count >= 3 and attachment_count >= 2:  # noqa: PLR2004
        return "Same message repeated across 3+ channels with multiple attachments"

    return None
