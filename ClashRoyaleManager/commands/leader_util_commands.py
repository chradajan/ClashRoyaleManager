"""Various utility commands intended for leadership."""

from enum import Enum
from typing import Literal

import discord
from discord import app_commands

import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG, log_message
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
    channel_id = db_utils.get_clan_affiliated_channel_id(clan.value)
    channel = interaction.guild.get_channel(channel_id)

    if channel is None:
        LOG.warning(log_message("Attempted to send reminder to channel that does not exist", channel_id=channel_id))
        embed = discord.Embed(title="Specified clan does not have an associated channel to send reminder to",
                              color=discord.Color.red())
    else:
        try:
            await discord_utils.send_reminder(clan.value, channel, ReminderTime.ALL, False)
            embed = discord.Embed(title="Reminder sent",
                                  description=(f"Reminder for members of {discord.utils.escape_markdown(clan.name)} sent to "
                                               f"#{discord.utils.escape_markdown(channel.name)}"),
                                  color=discord.Color.green())

            if interaction.channel == channel:
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
    await interaction.response.defer()
    if selection.value == "True":
        path = db_utils.export_all_clan_data(True, active_members_only)
    elif selection.value == "False":
        path = db_utils.export_all_clan_data(False, active_members_only)
    else:
        path = db_utils.export_clan_data(selection.value, selection.name, active_members_only, weeks)

    await interaction.followup.send(file=discord.File(path))
    LOG.command_end()


@app_commands.command()
@app_commands.describe(user="User to log a kick for")
@app_commands.describe(clan="Clan to associate the kick with")
async def clan_kick(interaction: discord.Interaction, user: str, clan: PRIMARY_CLANS):
    """Log that a user was kicked from a clan. Does NOT kick them from the Discord server."""
    LOG.command_start(interaction, user=user)
    member = discord_utils.get_member_from_mention(interaction, user)

    if member is not None:
        search_results = db_utils.get_user_in_database(member.id)
    else:
        search_results = db_utils.get_user_in_database(user)

    if not search_results:
        embed = discord_utils.user_not_found_embed(user)
    elif len(search_results) > 1:
        embed = discord_utils.duplicate_names_embed(search_results)
    else:
        player_tag, player_name, _ = search_results[0]
        success = db_utils.kick_user(player_tag, clan.value)
        player_name = discord.utils.escape_markdown(player_name)
        clan_name = discord.utils.escape_markdown(clan.name)

        if success:
            embed = discord.Embed(title=f"A kick from {clan_name} has been logged for {player_name}",
                                  color=discord.Color.green())
        else:
            embed = discord.Embed(title=f"{player_name} was not found in the database",
                                  color=discord.Color.red())

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(user="User to undo the most recent kick for")
@app_commands.describe(clan="Remove the most recent kick associated with this clan")
async def undo_kick(interaction: discord.Interaction, user: str, clan: PRIMARY_CLANS):
    """Remove the most recent logged kick for a user."""
    LOG.command_start(interaction, user=user)
    member = discord_utils.get_member_from_mention(interaction, user)

    if member is not None:
        search_results = db_utils.get_user_in_database(member.id)
    else:
        search_results = db_utils.get_user_in_database(user)

    if not search_results:
        embed = discord_utils.user_not_found_embed(user)
    elif len(search_results) > 1:
        embed = discord_utils.duplicate_names_embed(search_results)
    else:
        player_tag, player_name, _ = search_results[0]
        player_name = discord.utils.escape_markdown(player_name)
        clan_name = discord.utils.escape_markdown(clan.name)
        undone_kick = db_utils.undo_kick(player_tag, clan.value)

        if undone_kick is None:
            embed = discord.Embed(title=f"{player_name} was either not found or doesn't have any kicks",
                                  color=discord.Color.yellow())
        else:
            undone_kick = undone_kick.strftime("%Y-%m-%d")
            embed = discord.Embed(title=f"A kick on {undone_kick} from {clan_name} was undone for {player_name}",
                                  color=discord.Color.green())

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@send_reminder.error
@export.error
@clan_kick.error
@undo_kick.error
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
    clan_kick,
    undo_kick,
]
"""Commands to be added by leader_util_commands module."""
