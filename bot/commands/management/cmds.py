import discord
from discord import app_commands
from modules.bot import bot
from modules.checks import bot_owner_only
from modules.config import reload_settings
from modules.decorators import command_group
from modules.logger import logger


@command_group("cmd_group")
@bot_owner_only()
@app_commands.command(
    name="reload",
    description="Reload a bot command without restarting the bot.",
)
async def reload_command_command(interaction: discord.Interaction, command: str) -> None:
    try:
        await bot.reload_extension(f"commands.{command}")
        await bot.tree.sync()
        await interaction.response.send_message(
            content=f"Reloaded command: `{command}`",
            ephemeral=True,
        )
        logger.info(f"Reloaded command {command} via Discord")
    except Exception as e:  # noqa: BLE001
        await interaction.response.send_message(
            content=f"Failed to reload `commands.{command}`: {e!s}",
            ephemeral=True,
        )
        logger.exception(f"Failed to reload command {command} via Discord:")


@command_group("cmd_group")
@bot_owner_only()
@app_commands.command(
    name="unload",
    description="Unload a bot command without restarting the bot.",
)
async def unload_command_command(interaction: discord.Interaction, command: str) -> None:
    try:
        await bot.unload_extension(f"commands.{command}")
        await bot.tree.sync()
        await interaction.response.send_message(
            content=f"Unloaded command: `{command}`",
            ephemeral=True,
        )
        logger.info(f"Unloaded command {command} via Discord")
    except Exception as e:  # noqa: BLE001
        await interaction.response.send_message(
            content=f"Failed to unload `commands.{command}`: {e!s}",
            ephemeral=True,
        )
        logger.exception(f"Failed to unload command {command} via Discord:")


@command_group("cmd_group")
@bot_owner_only()
@app_commands.command(
    name="load",
    description="Load a bot command without restarting the bot.",
)
async def load_command_command(interaction: discord.Interaction, command: str) -> None:
    try:
        await bot.load_extension(f"commands.{command}")
        await bot.tree.sync()
        await interaction.response.send_message(
            content=f"Loaded command: `{command}`",
            ephemeral=True,
        )
        logger.info(f"Loaded command {command} via Discord")
    except Exception as e:  # noqa: BLE001
        await interaction.response.send_message(
            content=f"Failed to load `commands.{command}`: {e!s}",
            ephemeral=True,
        )
        logger.exception(f"Failed to load command {command} via Discord:")


@command_group("cmd_group")
@bot_owner_only()
@app_commands.command(
    name="list",
    description="List currently loaded bot commands.",
)
async def list_commands_command(interaction: discord.Interaction) -> None:
    try:
        extensions = list(bot.extensions)

        if not extensions:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="No Commands Loaded",
                    description="There are currently no commands loaded.",
                    color=discord.Color.yellow(),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Loaded Commands",
                description="\n".join([
                    f"- `{ext}`" for ext in extensions
                ]),
                color=discord.Color.blue(),
            ),
            ephemeral=True,
        )
    except Exception as e:  # noqa: BLE001
        await interaction.response.send_message(
            content=f"Failed to list commands: {e!s}",
            ephemeral=True,
        )
        logger.exception("Failed to list commands via Discord:")


@command_group("settings_group")
@bot_owner_only()
@app_commands.command(
    name="reload",
    description="Reload the bot's settings",
)
async def reload_config_command(interaction: discord.Interaction) -> None:
    try:
        new = reload_settings()
        bot.settings = new
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Settings Reloaded",
                description="Bot settings reloaded successfully.",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )
        logger.info("Bot settings reloaded via Discord")
    except Exception as e:  # noqa: BLE001
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Settings Reload Failed",
                description=f"Failed to reload bot settings: {e!s}",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        logger.exception("Failed to reload bot settings via Discord:")
