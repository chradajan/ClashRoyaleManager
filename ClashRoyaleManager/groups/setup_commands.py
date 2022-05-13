"""Slash commands for setting up Discord server."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.setup_utils as setup_utils
from utils.custom_types import ClanRole, SpecialRole, StrikeCriteria
from utils.exceptions import GeneralAPIError, ResourceNotFound

class SetupCommands(app_commands.Group, name="setup"):
    """Commands for first time Discord server setup."""

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(clan_role="Clan role to associate with a Discord role")
    @app_commands.describe(discord_role="Discord role to give based on a user's clan role")
    async def register_clan_role(self, interaction: discord.Interaction, clan_role: ClanRole, discord_role: discord.Role):
        """Register a role for users to receive based on their in-game clan role."""
        setup_utils.set_clan_role(clan_role, discord_role)
        embed = discord.Embed(title=(f"Users that are {clan_role.value}s in their respective clans "
                                     f"will now receive the {discord_role} role."),
                              color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @register_clan_role.error
    async def register_clan_role_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """register_clan_role error handler"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            raise error

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(special_status="Special status to associate with a Discord role")
    @app_commands.describe(discord_role="Discord role to give based on a user's special status")
    async def register_special_clan_role(self,
                                         interaction: discord.Interaction,
                                         special_status: SpecialRole,
                                         discord_role: discord.Role):
        """Register a role for users that are not members of any of the primary clans."""
        setup_utils.set_special_role(special_status, discord_role)

        if special_status == SpecialRole.Visitor:
            embed = discord.Embed(title=("Users that are not a member of any of the primary clans "
                                         f"will now receive the {discord_role} role."),
                                  color=discord.Color.green())
        elif special_status == SpecialRole.New:
            embed = discord.Embed(title=f"Users will now receive the {discord_role} role upon joining the server.",
                                  color=discord.Color.green())
        elif special_status == SpecialRole.Rules:
            embed = discord.Embed(title=f"Users will now receive the {discord_role} role when they need to acknowledge the rules.",
                                  color=discord.Color.green())
        elif special_status == SpecialRole.Admin:
            embed = discord.Embed(title=f"Users with access to privileged commands should now receive the {discord_role} role.",
                                  color=discord.Color.green())
        else:
            embed = discord.Embed(title="Received an improper status. No changes have been made.", color=discord.Color.red())

        await interaction.response.send_message(embed=embed)

    @register_special_clan_role.error
    async def register_special_clan_role_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """register_special_clan_role error handler"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            raise error


    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(tag="Tag of clan to designate as a primary clan")
    @app_commands.describe(role="Discord role to assign members of this clan")
    @app_commands.describe(track_stats="Whether to track deck usage and Battle Day stats of clan")
    @app_commands.describe(send_reminders="Whether to send automated reminders to members of the clan on Battle Days")
    @app_commands.describe(assign_strikes="Whether to assign automated strikes to members of the clan based on low participation")
    @app_commands.describe(strike_type="Whether to give strikes based on insufficient deck usage or low medal counts")
    @app_commands.describe(strike_threshold="Decks needed per Battle Day or total medals needed to avoid receiving a strike")
    async def register_primary_clan(self,
                                    interaction: discord.Interaction,
                                    tag: str,
                                    role: discord.Role,
                                    track_stats: bool,
                                    send_reminders: bool,
                                    assign_strikes: bool,
                                    strike_type: StrikeCriteria,
                                    strike_threshold: app_commands.Range[int, 0, 3600]):
        """Designate a clan as a primary clan."""
        processed_tag = clash_utils.process_clash_royale_tag(tag)
        
        if processed_tag is None:
            embed = discord.Embed(title="You entered an invalid Supercell tag. Please try again.", color=discord.Color.red())
        else:
            try:
                name = setup_utils.set_primary_clan(processed_tag,
                                                 role,
                                                 track_stats,
                                                 send_reminders,
                                                 assign_strikes,
                                                 strike_type,
                                                 strike_threshold)
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

    @register_primary_clan.error
    async def register_primary_clan_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """register_primary_clan error handler"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            raise error


    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(tag="Tag of the clan you wish to no longer be designated as a primary clan")
    async def unregister_primary_clan(self, interaction: discord.Interaction, tag: str):
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

    @unregister_primary_clan.error
    async def unregister_primary_clan_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """unregister_primary_clan error handler"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            raise error


    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def complete_setup(self, interaction: discord.Interaction):
        """Once all roles and primary clans are set, use this command to complete the setup process."""
        unset_clan_roles = setup_utils.get_unset_clan_roles()
        unset_special_roles = setup_utils.get_unset_special_roles()
        is_primary_clan_set = setup_utils.is_primary_clan_set()

        if unset_clan_roles:
            embed = discord.Embed(title="Cannot complete setup yet. The following clan roles do not have Discord roles:",
                                  description="```" + ", ".join(role.name for role in unset_clan_roles) + "```",
                                  color=discord.Color.red())
        elif unset_special_roles:
            embed = discord.Embed(title="Cannot complete setup yet. The following special roles do not have Discord roles:",
                                  description="```" + ", ".join(role.name for role in unset_special_roles) + "```",
                                  color=discord.Color.red())
        elif not is_primary_clan_set:
            embed = discord.Embed(title="Cannot complete setup yet. There must be at least one primary clan.",
                                  color=discord.Color.red())
        else:
            try:
                setup_utils.finish_setup()
                embed = discord.Embed(title="Setup complete. The bot must now be restarted.", color=discord.Color.green())
            except GeneralAPIError:
                embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                                      description="Please try again later.",
                                      color = discord.Color.red())

        await interaction.response.send_message(embed=embed)

    @complete_setup.error
    async def complete_setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """complete_setup error handler"""
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(title="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
