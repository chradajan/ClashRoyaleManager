"""Commands to give, remove, and check strikes."""

import discord
from discord import app_commands

import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.custom_types import SpecialChannel

@app_commands.command()
@app_commands.describe(user="User to give a strike to")
async def give_strike(interaction: discord.Interaction, user: str):
    """Give a strike to the specified user."""
    LOG.command_start(interaction, user=user)
    member = discord_utils.get_member_from_mention(interaction, user)
    tag_user = interaction.channel != CHANNEL[SpecialChannel.Strikes]

    if member is not None:
        embed = await discord_utils.update_strikes_helper(member.id, member.display_name, 1, tag_user)
    else:
        search_results = db_utils.get_user_in_database(user)

        if not search_results:
            embed = discord_utils.user_not_found_embed(user)
        elif len(search_results) > 1:
            embed = discord_utils.duplicate_names_embed(search_results)
        else:
            tag, name, _ = search_results[0]
            embed = await discord_utils.update_strikes_helper(tag, name, 1, tag_user)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(user="User to remove a strike from")
async def remove_strike(interaction: discord.Interaction, user: str):
    """Remove a strike from the specified user."""
    LOG.command_start(interaction, user=user)
    member = discord_utils.get_member_from_mention(interaction, user)
    tag_user = interaction.channel != CHANNEL[SpecialChannel.Strikes]

    if member is not None:
        embed = await discord_utils.update_strikes_helper(member.id, member.display_name, -1, tag_user)
    else:
        search_results = db_utils.get_user_in_database(user)

        if not search_results:
            embed = discord_utils.user_not_found_embed(user)
        elif len(search_results) > 1:
            embed = discord_utils.duplicate_names_embed(search_results)
        else:
            tag, name, _ = search_results[0]
            embed = await discord_utils.update_strikes_helper(tag, name, -1, tag_user)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
async def strikes(interaction: discord.Interaction):
    """Check how many strikes you have."""
    LOG.command_start(interaction)
    strikes = db_utils.get_strike_count(interaction.user.id)

    if strikes < 2:
        color = discord.Color.green()
    elif strikes < 4:
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()

    embed = discord.Embed(title=f"You have {strikes} strikes.", color=color)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


STRIKE_COMMANDS = [
    give_strike,
    remove_strike,
    strikes,
]
"""Commands to be added by strike_commands module."""
