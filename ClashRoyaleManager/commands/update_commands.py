"""Slash commands for registering and updating status."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.custom_types import SpecialRole
from utils.exceptions import GeneralAPIError, ResourceNotFound
from utils.role_manager import ROLE


@app_commands.command()
@app_commands.checks.cooldown(3, 10.0)
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

                LOG.info("User successfully registered")
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


@app_commands.command()
@app_commands.checks.cooldown(1, 10.0)
async def update(interaction: discord.Interaction):
    """Update your roles and nickname based on your current Clash Royale username and clan affiliation."""
    LOG.command_start(interaction)
    success = await discord_utils.update_member(interaction.user, True)

    if success:
        embed = discord.Embed(title="Update successful!",
                              description=("Your Discord nickname should now match your Clash Royale username and your roles should"
                                           " reflect your current clan affiliation."),
                              color=discord.Color.green())
    else:
        embed = discord.Embed(title="Something went wrong updating your information.",
                              description="This could be because you are unregistered. Make sure to use the `/register` command",
                              color=discord.Color.red())

    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 10.0)
@app_commands.describe(member="Discord member to update roles and nickname of")
async def update_member(interaction: discord.Interaction, member: discord.Member):
    """Update another member so that their roles and nickname reflect their current Clash Royale username and clan affiliation."""
    LOG.command_start(interaction, member=member)
    success = await discord_utils.update_member(member, True)

    if success:
        embed = discord.Embed(title="Update successful!",
                              description=(f"{member}'s nickname should now match their Clash Royale username and their roles "
                                           "should reflect their current clan affiliation."),
                              color=discord.Color.green())
    else:
        embed = discord.Embed(title="Something went wrong updating their information.",
                              description=("This could be because they are unregistered. Make sure they've used the `/register` "
                                           "command"),
                              color=discord.Color.red())

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 30.0)
async def update_all_members(interaction: discord.Interaction):
    """Update any members on the Discord server whose roles/nicknames do not reflect their current in-game status."""
    LOG.command_start(interaction)
    await discord_utils.update_all_members(interaction.guild)
    embed = discord.Embed(title="Update complete. All members' roles and nicknames should reflect their current in-game status.",
                          color=discord.Color.green())
    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 10.0)
@app_commands.describe(member="Member to unregister")
async def unregister_member(interaction: discord.Interaction, member: discord.Member):
    """Remove another member's roles and assign them the new member role."""
    LOG.command_start(interaction, member=member)
    db_utils.dissociate_discord_info_from_user(member)
    await discord_utils.reset_to_new(member)
    embed = discord.Embed(title=f"{member} has had their roles stripped and assigned the new member role",
                          color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 720.0)
async def unregister_all_members(interaction: discord.Interaction):
    """Remove roles from all members on the server and assign everyone the new member role."""
    LOG.command_start(interaction)
    await interaction.response.defer()
    count = 0

    for member in interaction.guild.members:
        if member.bot:
            continue

        count += 1
        db_utils.dissociate_discord_info_from_user(member)
        await discord_utils.reset_to_new(member)

    embed = discord.Embed(title=f"Unregister all members complete. {count} members have been reset.")
    await interaction.followup.send(embed=embed)


@register.error
@update.error
@update_member.error
@update_all_members.error
@unregister_member.error
@unregister_all_members.error
async def update_commands_error_hander(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for update commands."""
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


UPDATE_COMMANDS = [
    register,
    update,
    update_member,
    update_all_members,
    unregister_member,
    unregister_all_members,
]
"""Commands to be added by member_commands module."""
