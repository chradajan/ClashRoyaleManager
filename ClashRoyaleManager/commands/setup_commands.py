"""Slash commands for setting up Discord server."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.setup_utils as setup_utils
from log.logger import LOG
from utils.custom_types import ClanRole, SpecialChannel, SpecialRole
from utils.exceptions import GeneralAPIError, ResourceNotFound


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(clan_role="Clan role to associate with a Discord role")
@app_commands.describe(discord_role="Discord role to give based on a user's clan role")
async def register_clan_role(interaction: discord.Interaction, clan_role: ClanRole, discord_role: discord.Role):
    """Register a role for users to receive based on their in-game clan role."""
    setup_utils.set_clan_role(clan_role, discord_role)
    embed = discord.Embed(title=(f"Users that are {clan_role.value}s in their respective clans "
                                 f"will now receive the {discord_role} role."),
                            color=discord.Color.green())
    await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(special_status="Special status to associate with a Discord role")
@app_commands.describe(discord_role="Discord role to give based on a user's special status")
async def register_special_role(interaction: discord.Interaction, special_status: SpecialRole, discord_role: discord.Role):
    """Register a role for New members and Visitors."""
    setup_utils.set_special_role(special_status, discord_role)

    if special_status == SpecialRole.Visitor:
        embed = discord.Embed(title=("Users that are not a member of any of the primary clans "
                                     f"will now receive the {discord_role} role."),
                                color=discord.Color.green())
    elif special_status == SpecialRole.New:
        embed = discord.Embed(title=f"Users will now receive the {discord_role} role upon joining the server.",
                                color=discord.Color.green())
    else:
        embed = discord.Embed(title="Received invalid status. No changes have been made.", color=discord.Color.red())

    await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel_purpose="Whether this channel is for kicks, new member info, rules, or strikes")
@app_commands.describe(channel="Discord text channel where notifications regarding the specified purpose will be sent")
async def register_special_channel(interaction: discord.Interaction,
                                   channel_purpose: SpecialChannel,
                                   channel: discord.TextChannel):
    """Set text channels used for Kicks, New Member Info, Rules, and Strikes."""
    if interaction.client.user not in channel.members:
        embed = discord.Embed(title=f"ClashRoyaleManager needs to be a member of #{channel} in order to send messages.",
                              description="Either add ClashRoyaleManager to the channel or choose a different channel.",
                              color=discord.Color.red())
    elif channel_purpose == SpecialChannel.Rules and not channel.permissions_for(channel.guild.me).manage_messages:
        embed = discord.Embed(title=f"ClashRoyaleManager requires the `Manage Messages` permission for the selected Rules channel",
                              description=(f"Either give ClashRoyaleManager permission to manage messages in #{channel} or choose "
                                           "a different channel."),
                              color=discord.Color.red())
    elif channel_purpose != SpecialChannel.Rules and not channel.permissions_for(channel.guild.me).send_messages:
        embed = discord.Embed(title=f"ClashRoyaleManager does not have permission to send messages in #{channel}",
                              description=("Either give ClashRoyaleManager permission to send messages there "
                                           "or choose a different channel."),
                              color=discord.Color.red())
    else:
        setup_utils.set_special_channel(channel_purpose, channel)

        if channel_purpose == SpecialChannel.Kicks:
            embed = discord.Embed(title=f"Kick screenshots can now be posted in #{channel}", color=discord.Color.green())
        elif channel_purpose == SpecialChannel.NewMemberInfo:
            embed = discord.Embed(title=f"Stats about newly registered members will now be sent to #{channel}",
                                  color=discord.Color.green())
        elif channel_purpose == SpecialChannel.Rules:
            embed = discord.Embed(title=f"New members should now register in #{channel}. Non-admin messages there will be deleted.",
                                  color=discord.Color.green())
        elif channel_purpose == SpecialChannel.Strikes:
            embed = discord.Embed(title=f"Strike notifications will now be sent to #{channel}", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Received invalid channel type. No changes have been made.", color=discord.Color.red())

    await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(tag="Tag of clan to designate as a primary clan")
@app_commands.describe(role="Discord role assigned to members of this clan")
@app_commands.describe(channel="Discord text channel associated with this clan")
@app_commands.describe(track_stats="Whether to track deck usage and Battle Day stats of clan")
@app_commands.describe(send_reminders="Whether to send automated reminders to members of the clan on Battle Days")
@app_commands.describe(assign_strikes="Whether to assign automated strikes to members of the clan based on low participation")
@app_commands.describe(required_decks="Decks needed per war day")
async def register_primary_clan(interaction: discord.Interaction,
                                tag: str,
                                role: discord.Role,
                                channel: discord.TextChannel,
                                track_stats: bool,
                                send_reminders: bool,
                                assign_strikes: bool,
                                required_decks: app_commands.Range[int, 0, 4]):
    """Designate a clan as a primary clan."""
    processed_tag = clash_utils.process_clash_royale_tag(tag)
    
    if processed_tag is None:
        embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
    else:
        try:
            name = setup_utils.set_primary_clan(processed_tag,
                                                role,
                                                channel,
                                                track_stats,
                                                send_reminders,
                                                assign_strikes,
                                                required_decks)
            embed = discord.Embed(title=f"{name} has been successfully registered as a primary clan.",
                                  color=discord.Color.green())
        except GeneralAPIError:
            embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                                  description="Please try again later.",
                                  color = discord.Color.red())
        except ResourceNotFound:
            embed = discord.Embed(title="The tag you entered does not exist.",
                                  description="Please enter a valid clan tag.",
                                  color=discord.Color.red())

    await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(tag="Tag of the clan you wish to no longer be designated as a primary clan")
async def unregister_primary_clan(interaction: discord.Interaction, tag: str):
    """Remove a clan from the list of primary clans."""
    processed_tag = clash_utils.process_clash_royale_tag(tag)

    if processed_tag is None:
        embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
    else:
        name = setup_utils.remove_primary_clan(processed_tag)

        if name is None:
            embed = discord.Embed(title="The tag you entered did not match that of any primary clans.",
                                  description="No changes have been made.",
                                  color=discord.Color.red())
        else:
            embed = discord.Embed(title=f"{name} is no longer designated as a primary clan.", color=discord.Color.green())

    await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(season="Current Clash Royale season")
async def finish_setup(interaction: discord.Interaction, season: int):
    """Once all roles and primary clans are set, use this command to complete the setup process."""
    unset_clan_roles = setup_utils.get_unset_clan_roles()
    unset_special_roles = setup_utils.get_unset_special_roles()
    unset_special_channels = setup_utils.get_unset_special_channels()
    is_primary_clan_set = setup_utils.is_primary_clan_set()

    if unset_clan_roles:
        embed = discord.Embed(title="Cannot complete setup yet. The following clan roles do not have Discord roles:",
                              description="```" + ", ".join(role.name for role in unset_clan_roles) + "```",
                              color=discord.Color.red())
    elif unset_special_roles:
        embed = discord.Embed(title="Cannot complete setup yet. The following special roles do not have Discord roles:",
                              description="```" + ", ".join(role.name for role in unset_special_roles) + "```",
                              color=discord.Color.red())
    elif unset_special_channels:
        embed = discord.Embed(title="Cannot complete setup yet. The following special channels are not set:",
                              description="```" + ", ".join(channel.name for channel in unset_special_channels) + "```",
                              color=discord.Color.red())
    elif not is_primary_clan_set:
        embed = discord.Embed(title="Cannot complete setup yet. There must be at least one primary clan.",
                              color=discord.Color.red())
    else:
        try:
            setup_utils.finish_setup(season)
            embed = discord.Embed(title="Setup complete. The bot must now be restarted.", color=discord.Color.green())
        except GeneralAPIError:
            embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                                  description="Please try again later.",
                                  color = discord.Color.red())

    await interaction.response.send_message(embed=embed)


@register_clan_role.error
@register_special_role.error
@register_special_channel.error
@register_primary_clan.error
@unregister_primary_clan.error
@finish_setup.error
async def setup_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for setup commands."""
    if isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        LOG.exception(error)


SETUP_COMMANDS = [
    register_clan_role,
    register_special_role,
    register_special_channel,
    register_primary_clan,
    unregister_primary_clan,
    finish_setup,
]
"""Commands to be added by setup_commands module."""
