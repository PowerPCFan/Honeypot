from datetime import UTC, datetime, timedelta

import discord
from modules.config import Settings, load_settings
from modules.logger import logger
from modules.models import ModerationAction, SpamCategory
from modules.notifications import (
    dm_before_kick,
    send_honeypot_notification,
    send_spam_notification,
)
from modules.scoring import assess_message
from modules.state import MessageMemory


class HoneypotBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        super().__init__(intents=discord.Intents.all())

        self.settings = settings
        self.memory = MessageMemory(
            db_path=settings.history_db.path,
            retention_days=settings.history_db.retention_days,
        )

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")
        guild = self.get_guild(self.settings.guild_id)
        if guild is None:
            logger.warning("Configured guild %s is not currently available", self.settings.guild_id)
        else:
            logger.info("Monitoring guild: %s (%s)", guild.name, guild.id)

    async def on_message(self, message: discord.Message) -> None:  # noqa: C901, PLR0911
        if message.guild is None:
            return

        if message.guild.id != self.settings.guild_id:
            return

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

        if self.memory.was_honeypot_caught(message.author.id):
            self._record_message(message, is_clean=False)
            return

        if message.author.bot:
            return

        if not isinstance(message.author, discord.Member):
            return

        assessment = assess_message(message, self.memory, self.settings)
        if assessment.category is SpamCategory.NONE:
            self._record_message(message, is_clean=True)
            return

        await send_spam_notification(message, assessment, self.settings)
        if self.settings.message_deletion.on_detected_spam:
            await self._delete_message(message)

        if assessment.should_moderate:
            dm_sent = await dm_before_kick(message.author, self.settings)
            await self._apply_action(
                message.author,
                self.settings.action,
                reason=assessment.certain_reason or "100% spam detected",
            )
            if self._should_delete_user_messages_after_action(assessment.category):
                await self._delete_recent_user_messages(
                    message.guild,
                    message.author.id,
                )
            logger.info(
                "Applied %s to %s (%s) for spam. DM sent: %s",
                self.settings.action.value,
                message.author,
                message.author.id,
                dm_sent,
            )

        self._record_message(message, is_clean=False)

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

        await send_honeypot_notification(message, self.settings, dm_sent=None)
        dm_sent = await dm_before_kick(member, self.settings, honeypot=True)
        await self._apply_action(
            member,
            self.settings.honeypot.action,
            reason="Posted in honeypot channel",
        )
        if (
            self.settings.message_deletion.on_action
            and self.settings.honeypot.action in {ModerationAction.KICK, ModerationAction.BAN}
            and message.guild is not None
        ):
            await self._delete_recent_user_messages(
                message.guild,
                member.id,
            )
        logger.info(
            "Applied %s to %s (%s) for honeypot trigger. DM sent: %s",
            self.settings.honeypot.action.value,
            member,
            member.id,
            dm_sent,
        )

    @staticmethod
    async def _apply_action(
        member: discord.Member,
        action: ModerationAction,
        *,
        reason: str,
    ) -> None:
        try:
            if action is ModerationAction.TIMEOUT:
                until = datetime.now(tz=UTC) + timedelta(seconds=3600)
                await member.timeout(until, reason=reason)
            elif action is ModerationAction.KICK:
                await member.kick(reason=reason)
            elif action is ModerationAction.BAN:
                await member.ban(reason=reason, delete_message_days=0)
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

    def _should_delete_user_messages_after_action(self, category: SpamCategory) -> bool:
        deletion = self.settings.message_deletion
        return (
            deletion.on_action
            and self.settings.action in {ModerationAction.KICK, ModerationAction.BAN}
            and category.rank >= deletion.on_action_min_category.rank
        )

    async def _delete_recent_user_messages(
        self,
        guild: discord.Guild,
        user_id: int,
    ) -> None:
        limit = self.settings.message_deletion.on_action_del_limit
        deleted_count = 0
        channels = [*guild.text_channels, *guild.threads]

        for channel in channels:
            if deleted_count >= limit:
                break

            try:
                async for candidate in channel.history(limit=100):
                    if deleted_count >= limit:
                        break
                    if candidate.author.id != user_id:
                        continue

                    await self._delete_message(candidate)
                    deleted_count += 1
            except discord.Forbidden:
                logger.exception("Missing permissions to read/delete messages in %s", channel)
            except discord.HTTPException:
                logger.exception("Discord rejected message history/deletion in %s", channel)

        logger.info("Deleted %s recent messages from user %s", deleted_count, user_id)

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
        await super().close()


def main() -> None:
    settings = load_settings()
    bot = HoneypotBot(settings)
    bot.run(settings.token)


if __name__ == "__main__":
    main()
