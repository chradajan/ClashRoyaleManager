"""Slash commands available to any member."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG, log_message
from utils.custom_types import SpecialRole
from utils.exceptions import GeneralAPIError, ResourceNotFound
from utils.role_manager import ROLE


@app_commands.command()
@app_commands.describe(tag="Your player tag")
async def register(interaction: discord.Interaction, tag: str):
    """Enter your player tag to be registered to the database."""
    LOG.command_start(interaction, tag=tag)

    processed_tag = clash_utils.process_clash_royale_tag(tag)

    if ROLE[SpecialRole.New] not in interaction.user.roles:
        LOG.debug("User without New role tried to register")
        embed = discord.Embed(title="You must be a new member to use this command.", color=discord.Color.red())
    elif processed_tag is None:
        LOG.debug("User provided invalid player tag")
        embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
    elif processed_tag in (clans := db_utils.get_clans_in_database()):
        LOG.debug("User provided tag of clan in database")
        embed = discord.Embed(title=f"You entered the clan tag of {clans[processed_tag]}. Please enter your own player tag.")
    elif db_utils.get_user_in_database(interaction.user.id):
        LOG.debug("Registered user tried to register again")
        embed = discord.Embed(title="You are already registered.", color=discord.Color.red())
    else:
        try:
            clash_data = clash_utils.get_clash_royale_user_data(processed_tag)

            if db_utils.insert_new_user(clash_data, interaction.user):
                try:
                    await interaction.user.edit(nick=clash_data['name'])
                except discord.errors.Forbidden:
                    pass

                await interaction.user.remove_roles(ROLE[SpecialRole.New])
                await discord_utils.assign_roles(interaction.user)

                LOG.info(log_message("User successfully registered", clash_data=clash_data))
                embed = discord.Embed(title="Registration successful!",
                                        description=f"You have been registered as {clash_data['name']}.",
                                        color=discord.Color.green())
            else:
                LOG.debug("User entered tag of existing registered user")
                embed = discord.Embed(title="The tag you entered is already associated with a user on this server.",
                                        description="If the tag you entered belongs to you, contact an Admin for help.",
                                        color=discord.Color.red())
        except GeneralAPIError:
            LOG.warning("API issue during user registration")
            embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                                    description="Please try again later.",
                                    color=discord.Color.red())
        except ResourceNotFound:
            LOG.debug("User entered tag that does not exist")
            embed = discord.Embed(title="The tag you entered does not exist.",
                                    description="Please enter your unique player tag.",
                                    color=discord.Color.red())

    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


MEMBER_COMMANDS = [
    register,
]
"""Commands to be added by member_commands module."""
