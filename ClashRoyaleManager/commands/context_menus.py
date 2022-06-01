"""Context menu commands."""

import discord
from discord import app_commands

import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.exceptions import GeneralAPIError

@app_commands.context_menu(name="Update")
@app_commands.checks.cooldown(1, 10.0)
async def update_context_menu(interaction: discord.Interaction, member: discord.Member):
    """Update this member's roles and nickname based on their current Clash Royale username and clan affiliation."""
    LOG.command_start(interaction, target=member)
    success = await discord_utils.update_member(member, True)

    if success:
        embed = discord.Embed(title="Update successful!",
                              description=("Their Discord nickname should now match their Clash Royale username and their roles "
                                           "should reflect their current clan affiliation."),
                              color=discord.Color.green())
    else:
        embed = discord.Embed(title="Something went wrong updating their information.",
                              description=("This could be because their are unregistered. Make sure they've used the `/register` "
                                           "command"),
                              color=discord.Color.red())

    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@app_commands.context_menu(name="Give Strike")
async def give_strike_context_menu(interaction: discord.Interaction, member: discord.Member):
    """Give a strike to this member."""
    LOG.command_start(interaction, target=member)
    embed = await discord_utils.update_strikes_helper(member.id, member.display_name, 1)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@app_commands.context_menu(name="Remove Strike")
async def remove_strike_context_menu(interaction: discord.Interaction, member: discord.Member):
    """Remove a strike from this member."""
    LOG.command_start(interaction, target=member)
    embed = await discord_utils.update_strikes_helper(member.id, member.display_name, -1)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@update_context_menu.error
async def context_menus_error_hander(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for setup commands."""
    if isinstance(error, GeneralAPIError):
        embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                              description="Please try again later.",
                              color=discord.Color.red())
    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(title="You've used this command too many times and it is currently on cooldown.",
                              color=discord.Color.red())
    else:
        embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
        LOG.exception(error)

    await interaction.response.send_message(embed=embed, ephemeral=True)


CONTEXT_MENUS = [
    update_context_menu,
    give_strike_context_menu,
    remove_strike_context_menu,
]
"""Context menu commands."""
