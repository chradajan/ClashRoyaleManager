"""Slash commands for registering and updating status."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.custom_types import ReminderTime, SpecialRole
from utils.exceptions import GeneralAPIError, ResourceNotFound
from utils.channel_manager import CHANNEL, SpecialChannel
from utils.role_manager import ROLE


@app_commands.command()
@app_commands.checks.cooldown(3, 10.0)
@app_commands.describe(tag="Your player tag")
async def register(interaction: discord.Interaction, tag: str):
    """Enter your player tag to be registered to the database."""
    LOG.command_start(interaction, tag=tag)
    processed_tag = clash_utils.process_clash_royale_tag(tag)

    if processed_tag is None:
        LOG.debug("User provided invalid player tag")
        embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
    elif processed_tag in (clans := db_utils.get_clans_in_database()):
        LOG.debug("User provided tag of clan in database")
        embed = discord.Embed(title=(f"You entered the clan tag of {discord.utils.escape_markdown(clans[processed_tag])}. "
                                     "Please enter your own player tag."))
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
                new_member_embed = discord_utils.create_card_levels_embed(clash_data)
                await CHANNEL[SpecialChannel.NewMemberInfo].send(embed=new_member_embed)
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
    await interaction.response.defer()
    db_utils.dissociate_discord_info_from_user(member)
    await discord_utils.reset_to_new(member)
    embed = discord.Embed(title=f"{member} has had their roles stripped and assigned the new member role",
                          color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 10.0)
@app_commands.describe(member="Member to register")
@app_commands.describe(tag="Player tag to register user to")
async def register_member(interaction: discord.Interaction, member: discord.Member, tag: str):
    """Manually register a Discord user. This is the same as that member using /register."""
    LOG.command_start(interaction, member=member)
    processed_tag = clash_utils.process_clash_royale_tag(tag)

    if processed_tag is not None:
        current_affiliation_id = db_utils.get_discord_id_from_player_tag(processed_tag)

    if processed_tag is None:
        embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
    elif processed_tag in (clans := db_utils.get_clans_in_database()):
        embed = discord.Embed(title=(f"You entered the clan tag of {discord.utils.escape_markdown(clans[processed_tag])}. "
                                     "Please enter your own player tag."))
    elif (current_affiliation_id is not None) and (current_affiliation_id != member.id):
        existing_member = discord.utils.get(interaction.guild.members, id=current_affiliation_id)
        embed = discord.Embed(title=f"That tag is already affiliated with {discord_utils.full_discord_name(existing_member)}.",
                              color=discord.Color.red())
    else:
        db_utils.dissociate_discord_info_from_user(member)

        try:
            clash_data = clash_utils.get_clash_royale_user_data(processed_tag)
            db_utils.insert_new_user(clash_data, member)

            try:
                await member.edit(nick=clash_data["name"])
            except discord.errors.Forbidden:
                pass

            await discord_utils.assign_roles(member)

            LOG.info("Member successfully registered manually")
            new_member_embed = discord_utils.create_card_levels_embed(clash_data)
            await CHANNEL[SpecialChannel.NewMemberInfo].send(embed=new_member_embed)
            discord_name = discord_utils.full_discord_name(member)

            embed = discord.Embed(title="Manual registration successful!",
                                  description=f"{discord_name} has been registered as {clash_data['name']}.",
                                  color=discord.Color.green())
        except GeneralAPIError:
            LOG.warning("API issue during manual user registration")
            embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                                  description="Please try again later.",
                                  color=discord.Color.red())
        except ResourceNotFound:
            LOG.debug("User entered tag that does not exist during manual registration")
            embed = discord.Embed(title="The tag you entered does not exist.",
                                  description="Please enter a valid player tag.",
                                  color=discord.Color.red())

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.checks.cooldown(1, 720.0)
@app_commands.describe(confirmation="""Enter "Yes I'm Sure" to issue command.""")
async def unregister_all_members(interaction: discord.Interaction, confirmation: str):
    """Remove roles from all members on the server and assign everyone the new member role. Type "Yes I'm Sure" to confirm."""
    LOG.command_start(interaction)
    await interaction.response.defer()

    if confirmation != "Yes I'm Sure":
        embed = discord.Embed(title="Invalid confirmation message. No users have been unregistered.",
                              description="Confirmation message must be spelled exactly as stated.",
                              color=discord.Color.red())
    else:
        count = 0

        for member in interaction.guild.members:
            if member.bot:
                continue

            count += 1
            db_utils.dissociate_discord_info_from_user(member)
            await discord_utils.reset_to_new(member)

        embed = discord.Embed(title=f"Unregister all members complete. {count} members have been reset.")

    await interaction.followup.send(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(reminder_time="When you would prefer to be pinged. ASIA = 13:30 UTC, EU = 19:00 UTC, US = 03:00 UTC")
@app_commands.choices(reminder_time=[
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU"),
    app_commands.Choice(name="ASIA", value="ASIA")
])
async def set_reminder_time(interaction: discord.Interaction, reminder_time: app_commands.Choice[str]):
    """Change when you get pinged for Battle Day reminders."""
    LOG.command_start(interaction, reminder_time=reminder_time)
    reminder_time = ReminderTime(reminder_time.value)
    db_utils.set_reminder_time(interaction.user.id, reminder_time)

    embed = discord.Embed(title="Update successful!",
                          description=f"You will now get pinged for automated {reminder_time.value} reminders.",
                          color=discord.Color.green())

    await interaction.response.send_message(embed=embed, ephemeral=True)
    LOG.command_end()


@register.error
@update.error
@update_member.error
@update_all_members.error
@unregister_member.error
@register_member.error
@unregister_all_members.error
@set_reminder_time.error
async def update_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
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
    register_member,
    unregister_all_members,
    set_reminder_time,
]
"""Commands to be added by member_commands module."""
