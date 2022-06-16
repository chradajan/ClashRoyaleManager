"""Various utility commands intended for leadership."""

from enum import Enum
from typing import Literal

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
    ephemeral = False

    try:
        await discord_utils.send_reminder(clan.value, ReminderTime.ALL)
        embed = discord.Embed(title="Reminder sent",
                              description=(f"Reminder for members of {discord.utils.escape_markdown(clan.name)} sent to "
                                           f"#{discord.utils.escape_markdown(CHANNEL[SpecialChannel.Reminders].name)}"),
                              color=discord.Color.green())

        if interaction.channel == CHANNEL[SpecialChannel.Reminders]:
            ephemeral = True
    except GeneralAPIError:
        embed = discord.Embed(title="Reminder failed to send",
                              description="The Clash Royale API is currently inaccessible.",
                              color=discord.Color.red())

    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    LOG.command_end()


export_enum_dict = {clan.name: clan.value for clan in PRIMARY_CLANS}
export_enum_dict["All primary clans"] = "True"
export_enum_dict["All users"] = "False"
EXPORT_ENUM = Enum("ExportEnum", export_enum_dict)

@app_commands.command()
@app_commands.describe(selection="Whether to include users in a specific primary clan, users in any primary clan, or all users")
@app_commands.describe(active_members_only="Whether to include current or past and current members of the selected clan")
@app_commands.describe(weeks="How many weeks of stats to include. Has no effect when not exporting a single primary clan")
async def export(interaction: discord.Interaction,
                 selection: EXPORT_ENUM,
                 active_members_only: bool,
                 weeks: Literal[1, 2, 3, 4, 5, 6]):
    """Export data to an Excel spreadsheet."""
    LOG.command_start(interaction, selection=selection, active_members_only=active_members_only, weeks=weeks)
    if selection.value == "True":
        path = db_utils.export_all_clan_data(True, active_members_only)
    elif selection.value == "False":
        path = db_utils.export_all_clan_data(False, active_members_only)
    else:
        path = db_utils.export_clan_data(selection.value, selection.name, active_members_only, weeks)

    await interaction.response.send_message(file=discord.File(path))
    LOG.command_end()


@send_reminder.error
@export.error
async def leader_util_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for leader util commands."""
    if isinstance(error, GeneralAPIError):
        embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                              description="Please try again later.",
                              color=discord.Color.red())
    else:
        embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
        LOG.exception(error)

    await interaction.response.send_message(embed=embed, ephemeral=True)


LEADER_UTIL_COMMANDS = [
    send_reminder,
    export,
]
"""Commands to be added by leader_util_commands module."""
