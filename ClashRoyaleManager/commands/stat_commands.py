"""Statistics related commands."""

import os
from typing import Set

import discord
from discord import app_commands

import statistics.deck_stats as deck_stats
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG

PRIMARY_CLANS = db_utils.get_primary_clans_enum()


@app_commands.command()
@app_commands.describe(clan="Optionally filter to only consider decks used by members of this clan")
async def top_decks(interaction: discord.Interaction, clan: PRIMARY_CLANS=None):
    """Get the best performing decks over the last 5 weeks within the clan family."""
    LOG.command_start(interaction, clan=clan)
    num_decks = 5
    clan_tag = None

    if clan is not None:
        clan_tag = clan.value

    best_decks = deck_stats.best_performing_decks(clan_tag=clan_tag)[0:num_decks]

    if len(best_decks) != num_decks:
        LOG.warning(f"Only found {len(best_decks)} decks while trying to get best decks.")
        error_embed = discord.Embed(title="There is not enough data to complete this request.",
                                    description="If you specified a clan, try leaving that parameter empty or choosing a different clan.",
                                    color=discord.Color.yellow())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    await interaction.response.defer()

    embed_colors = [(0x35, 0xd6, 0xed), (0x65, 0xdd, 0xef), (0x7a, 0xe5, 0xf5), (0x97, 0xeb, 0xf4), (0xc9, 0xf6, 0xff)]
    embeds, files = discord_utils.create_deck_embeds(interaction, best_decks, embed_colors)

    clan_str = "across the clan network" if clan_tag is None else f"in {clan.name}"

    header_embed = discord.Embed(title=f"These are the best performing war decks {clan_str} over the past 5 weeks.*",
                                 color=discord.Color.green())
    header_embed.set_footer(text="*decks must have been used a minimum of 10 times and results in special modes are not considered")

    embeds = [header_embed] + embeds

    await interaction.followup.send(files=files, embeds=embeds)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(clan="Optionally filter to only consider decks used by members of this clan")
async def suggest_war_decks(interaction: discord.Interaction, clan: PRIMARY_CLANS=None):
    """Get the top 4 unique war decks from the last 5 weeks."""
    LOG.command_start(interaction, clan=clan)
    clan_tag = None

    if clan is not None:
        clan_tag = clan.value

    war_decks = deck_stats.suggest_war_decks(clan_tag=clan_tag)

    if len(war_decks) != 4:
        LOG.warning(f"Only found {len(war_decks)} decks while trying to suggest war decks.")
        error_embed = discord.Embed(title="There is not enough data to complete this request.",
                                    description="If you specified a clan, try leaving that parameter empty or choosing a different clan.",
                                    color=discord.Color.yellow())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    await interaction.response.defer()

    embed_colors = [(0x00, 0xff, 0xff), (0x00, 0x80, 0xff), (0x00, 0x00, 0xff), (0x80, 0x00, 0xff)]
    embeds, files = discord_utils.create_deck_embeds(interaction, war_decks, embed_colors)

    clan_str = "across the clan network" if clan_tag is None else f"in {clan.name}"

    header_embed = discord.Embed(title=f"This is the best performing set of war decks {clan_str} over the past 5 weeks.*",
                                 color=discord.Color.green())
    header_embed.set_footer(text="*decks must have been used a minimum of 10 times and results in special modes are not considered")

    embeds = [header_embed] + embeds

    await interaction.followup.send(files=files, embeds=embeds)
    LOG.command_end()


@top_decks.error
@suggest_war_decks.error
async def stat_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommand):
    """Error handler for stat commands."""
    embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
    LOG.exception(error)
    try:
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.InteractionResponded:
        await interaction.followup.send(embed=embed, ephemeral=True)


STAT_COMMANDS = [
    top_decks,
    suggest_war_decks,
]
"""Commands to be added by stat_commands module."""
