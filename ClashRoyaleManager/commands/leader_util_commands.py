"""Various utility commands intended for leadership."""

import discord
from discord import app_commands

import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.custom_types import ReminderTime, SpecialChannel
from utils.exceptions import GeneralAPIError

PRIMARY_CLANS = db_utils.get_primary_clans_enum()

@app_commands.command()
@app_commands.describe(clan="Which clan to send a reminder for")
async def send_reminder(interaction: discord.Interaction, clan: PRIMARY_CLANS):
    """Send a reminder to members of a clan that have not used all their decks today."""
    LOG.command_start(interaction, clan=clan)

    try:
        await discord_utils.send_reminder(clan.value, ReminderTime.ALL, False)
        embed = discord.Embed(title="Reminder sent",
                          description=(f"Reminder for members of {discord.utils.escape_markdown(clan.name)} sent to "
                                       f"#{discord.utils.escape_markdown(CHANNEL[SpecialChannel.Reminders])}"),
                          color=discord.Color.green())
    except GeneralAPIError:
        embed = discord.Embed(title="Reminder failed to send",
                              description="The Clash Royale API is currently inaccessible.",
                              color=discord.Color.red())

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@send_reminder.error
async def leader_util_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for leader util commands."""
    embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
    LOG.exception(error)
    await interaction.response.send_message(embed=embed, ephemeral=True)


LEADER_UTIL_COMMANDS = [
    send_reminder,
]
"""Commands to be added by leader_util_commands module."""
