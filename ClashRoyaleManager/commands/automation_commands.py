"""Commands to toggle automated routines and view automation status of primary clans."""

import discord
from discord import app_commands

import utils.db_utils as db_utils
from log.logger import LOG
from utils.custom_types import AutomatedRoutine, StrikeType

PRIMARY_CLANS = db_utils.get_primary_clans_enum()

@app_commands.command()
@app_commands.describe(clan="Which clan to update")
@app_commands.describe(routine="Which automated task to change the status of")
@app_commands.describe(status="Whether to enable or disable the specified task")
async def set_automation_status(interaction: discord.Interaction, clan: PRIMARY_CLANS, routine: AutomatedRoutine, status: bool):
    """Enable/disable an automated task for a primary clan."""
    LOG.command_start(interaction, clan=clan, routine=routine, status=status)
    db_utils.set_automated_routine(clan.value, routine, status)
    embed = discord.Embed(title=f"Automation status updated for {discord.utils.escape_markdown(clan.name)}",
                          description=f"Automated {routine.name} are now {'ENABLED' if status else 'DISABLED'}",
                          color=discord.Color.green())
    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(clan="Which clan to update")
@app_commands.describe(strike_type="Whether players must earn a certain number of medals or use a certain number of decks per day")
@app_commands.describe(strike_threshold="How many medals users must earn or how many decks must be used per Battle Day")
async def set_participation_requirements(interaction: discord.Interaction,
                                         clan: PRIMARY_CLANS,
                                         strike_type: StrikeType,
                                         strike_threshold: app_commands.Range[int, 0, 3600]):
    """Update the participation requirements of a primary clan in order to not receive automated strikes."""
    LOG.command_start(interaction, clan=clan, strike_type=strike_type, strike_threshold=strike_threshold)
    db_utils.set_participation_requirements(clan.value, strike_type, strike_threshold)

    if strike_type == StrikeType.Medals:
        message = f"Members must now achieve {strike_threshold} medals to avoid receiving automated strikes."
    elif strike_type == StrikeType.Decks:
        message = f"Members must now use {strike_threshold} decks per Battle Day to avoid receiving automated strikes."

    embed = discord.Embed(title=f"Participation requirements updated for {discord.utils.escape_markdown(clan.name)}",
                          description=message,
                          color=discord.Color.green())
    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
async def check_automation_status(interaction: discord.Interaction):
    """Get the current status of each automated routine for all primary clans."""
    primary_clans = db_utils.get_primary_clans()
    embed = discord.Embed(title="Automation status", color=discord.Color.green())

    for clan in primary_clans:
        status = (
            "```"
            f"Reminders:   {'Enabled' if clan['send_reminders'] else 'Disabled'}\n"
            f"Stats:       {'Enabled' if clan['track_stats'] else 'Disabled'}\n"
            f"Strikes:     {'Enabled' if clan['assign_strikes'] else 'Disabled'}\n"
            f"Strike Type: {clan['strike_type'].name}\n"
            f"Threshold:   {clan['strike_threshold']}"
            "```"
        )
        embed.add_field(name=discord.utils.escape_markdown(clan["name"]), value=status, inline=False)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


AUTOMATION_COMMANDS = [
    set_automation_status,
    set_participation_requirements,
    check_automation_status,
]
"""Commands to be added by automation_commands module."""
