from __future__ import annotations

from datetime import UTC, datetime, timedelta

import discord
from discord import InteractionCallbackResponse
from discord.ext import commands

from .config import load_settings
from .global_vars import DRY_RUN
from .handlers import add_handlers
from .logger import logger
from .models import ModerationAction, SpamCategory
from .notifications import (
    dm_before_action,
    send_honeypot_notification,
    send_spam_notification,
)
from .scoring import assess_message
from .state import MessageMemory, WhitelistedUsers


class HoneypotBot(commands.Bot):
    def __init__(self) -> None:
        discord.VoiceClient.warn_nacl = False
        discord.VoiceClient.warn_dave = False

        self.settings = load_settings()

        super().__init__(command_prefix="h!", intents=discord.Intents.all())

        self.memory = MessageMemory(
            db_path=self.settings.history_db.path,
            retention_days=self.settings.history_db.retention_days,
        )
        self.whitelist = WhitelistedUsers(db_path=self.settings.whitelist_db.path)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)
        guild = self.get_guild(self.settings.guild_id)
        if guild is None:
            logger.warning("Configured guild %s is not currently available", self.settings.guild_id)
        else:
            logger.info("Guild: '%s' (ID: %s)", guild.name, guild.id)
        if DRY_RUN:
            logger.warning("DRY_RUN is enabled; timeout/kick/ban actions will only be logged")

        # add extensions if not already added
        extensions = [
            "commands.whitelist",
            "commands.management",
        ]
        currently_loaded: list[str] = list(self.extensions)
        for extension in extensions:
            try:
                if extension not in currently_loaded:
                    await self.load_extension(extension)
                    logger.info(f"Loaded extension {extension}")
                else:
                    logger.info(f"Extension {extension} is already loaded")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to load extension {extension}: {e}")
        try:
            await self.tree.sync()
            logger.info("Command tree synced successfully!")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to sync command tree:")

    async def on_message(self, message: discord.Message) -> None:  # noqa: C901, PLR0911
        if message.author.bot:
            return

        if message.guild is None:
            return

        if message.guild.id != self.settings.guild_id:
            return

        if self.whitelist.is_whitelisted(message.author.id):
            self._record_message(message, is_clean=True)
            return

        msg_nonl = message.content.replace("\n", " ")
        logger.debug(
            "Received message in #%s with content '%s' (User: @%s | Message ID: %s)",
            message.channel,
            (msg_nonl[:50] + "...") if len(msg_nonl) > 50 else msg_nonl,  # noqa: PLR2004
            message.author,
            message.id,
        )

        if (
            self.settings.honeypot.enabled
            and message.channel.id == self.settings.honeypot.channel_id
        ):
            self.memory.mark_honeypot_caught(message.author.id)
            self._record_message(message, is_clean=False)
            if message.author.bot:
                logger.info(
                    "Marked bot %s (%s) as honeypot caught",
                    message.author,
                    message.author.id,
                )
                return

            await self._kick_for_honeypot(message)
            return

        # if self.memory.was_honeypot_caught(message.author.id):
        #     self._record_message(message, is_clean=False)
        #     return

        if not isinstance(message.author, discord.Member):
            return

        assessment = assess_message(message, self.memory, self.settings)
        logger.debug(
            "Message %s (by @%s) was assessed:\n%s",
            message.id,
            message.author,
            assessment,
        )
        if assessment.category is SpamCategory.NONE:
            self._record_message(message, is_clean=True)
            return

        actions: list[str] = []

        if (
            self.settings.message_deletion.on_detected_spam
            and assessment.category.rank
            >= self.settings.message_deletion.on_detected_spam_min_category.rank
        ):
            await self._delete_message(message)
            actions.append("Message deleted")

        if assessment.should_moderate:
            dm_sent = await dm_before_action(message.author, self.settings)
            await self._apply_action(
                message.author,
                self.settings.action,
                assessment.category,
                reason=assessment.certain_reason or "100% spam detected",
            )
            actions.append(str(self.settings.action.value.title()))
            logger.info(
                "Applied %s to %s (%s) for spam. DM sent: %s",
                self.settings.action.value,
                message.author,
                message.author.id,
                dm_sent,
            )

        await send_spam_notification(message, assessment, self.settings, actions=actions or None)

        self._record_message(message, is_clean=False)

    @staticmethod
    async def no_perms(interaction: discord.Interaction) -> InteractionCallbackResponse:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Permission Denied",
                description="You do not have permission to use this command.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )

    async def _kick_for_honeypot(self, message: discord.Message) -> None:
        member = message.author
        if isinstance(member, discord.User):
            guild = self.get_guild(self.settings.guild_id)
            if guild is None:
                logger.error("Guild not found when trying to retrieve member object")
                return
            member = guild.get_member(member.id)

        if not member:
            logger.error(
                "Member object not found for user %s (%s)",
                message.author,
                message.author.id,
            )
            return

        actions: list[str] = []

        dm_sent = await dm_before_action(member, self.settings, honeypot=True)
        await self._apply_action(
            member,
            self.settings.honeypot.action,
            reason="Posted in honeypot channel",
        )
        actions.append(f"{self.settings.honeypot.action.value.title()}")
        logger.info(
            "Applied %s to %s (%s) for honeypot trigger. DM sent: %s",
            self.settings.honeypot.action.value,
            member,
            member.id,
            dm_sent,
        )

        await send_honeypot_notification(
            message,
            self.settings,
            dm_sent=dm_sent,
            actions=actions or None,
        )

    async def _apply_action(
        self,
        member: discord.Member,
        action: ModerationAction,
        category: SpamCategory | None = None,
        *,
        reason: str,
    ) -> None:
        if DRY_RUN:
            logger.warning(
                "DRY_RUN: would apply %s to %s (%s). Reason: %s",
                action.value,
                member,
                member.id,
                reason,
            )
            return

        try:
            if action is ModerationAction.TIMEOUT:
                until = datetime.now(tz=UTC) + timedelta(seconds=3600)
                await member.timeout(until, reason=reason)
            elif action is ModerationAction.KICK:
                await member.kick(reason=reason)
            elif action is ModerationAction.BAN:
                if (category and (
                    self.settings.message_deletion.on_action
                    and self.settings.action in {ModerationAction.KICK, ModerationAction.BAN}
                    and category.rank >= self.settings.message_deletion.on_action_min_category.rank
                )) or not category:
                    days = 7
                else:
                    days = 0

                await member.ban(reason=reason, delete_message_days=days)
        except discord.Forbidden:
            logger.exception(
                "Missing permissions to apply %s to %s (%s)",
                action.value,
                member,
                member.id,
            )
        except discord.HTTPException:
            logger.exception(
                "Discord rejected %s for %s (%s)",
                action.value,
                member,
                member.id,
            )

    async def _delete_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except discord.NotFound:
            return
        except discord.Forbidden:
            logger.exception("Missing permissions to delete message %s", message.id)
        except discord.HTTPException:
            logger.exception("Discord rejected deletion for message %s", message.id)

    def _record_message(self, message: discord.Message, *, is_clean: bool) -> None:
        self.memory.record_message(
            user_id=message.author.id,
            message_id=message.id,
            channel_id=message.channel.id,
            created_at=message.created_at,
            is_clean=is_clean,
        )

    async def close(self) -> None:
        self.memory.close()
        self.whitelist.close()
        await super().close()

# Global instance
bot = HoneypotBot()
add_handlers(bot)
