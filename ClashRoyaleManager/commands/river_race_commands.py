"""Commands to get River Race status information."""

import discord
from discord import app_commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
import utils.stat_utils as stat_utils
from log.logger import LOG
from utils.exceptions import GeneralAPIError

PRIMARY_CLANS = db_utils.get_primary_clans_enum()

@app_commands.command()
@app_commands.describe(clan="Which clan to make prediction for")
@app_commands.describe(historical_win_rates="Whether to use each clan's historical win rates or assume a 50% win rate")
@app_commands.describe(historical_deck_usage=("Whether to use each clan's historical average number of decks used or assume they "
                                              "use all remaining decks"))
async def predict(interaction: discord.Interaction, clan: PRIMARY_CLANS, historical_win_rates: bool, historical_deck_usage: bool):
    """Predict the final standings of the current Battle Day."""
    LOG.command_start(interaction,
                      clan=clan,
                      historical_win_rates=historical_win_rates,
                      historical_deck_usage=historical_deck_usage)
    if not db_utils.is_battle_time(clan.value):
        embed = discord.Embed(title="Predictions can only be made on Battle Days.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    predicted_outcomes = stat_utils.predict_race_outcome(clan.value, historical_win_rates, historical_deck_usage)

    if not predicted_outcomes:
        embed = discord.Embed(title="There was an error gathering data to make a prediction.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord_utils.create_prediction_embed(clan.value, predicted_outcomes)
    await interaction.response.send_message(embed=embed)

    LOG.command_end()


@app_commands.command()
@app_commands.describe(clan="Which clan to check the River Race status for")
async def river_race_status(interaction: discord.Interaction, clan: PRIMARY_CLANS):
    """Check how many decks each clan in a River Race has left to use today."""
    LOG.command_start(interaction, clan=clan)
    river_race_status = clash_utils.river_race_status(clan.value)
    embed = discord.Embed(title=f"{discord.utils.escape_markdown(clan.name)}'s River Race Status", color=discord.Color.random())

    for clan_status in river_race_status:
        embed.add_field(name=discord.utils.escape_markdown(clan_status["name"]),
                        value=("```"
                               f"Maximum remaining: {clan_status['total_remaining_decks']}\n"
                               f"Active remaining:  {clan_status['active_remaining_decks']}"
                               "```"),
                        inline=False)

    await interaction.response.send_message(embed=embed)


@predict.error
@river_race_status.error
async def river_race_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for River Race commands."""
    if isinstance(error, GeneralAPIError):
        embed = discord.Embed(title="The Clash Royale API is currently inaccessible.",
                              description="Please try again later.",
                              color=discord.Color.red())
    else:
        embed = discord.Embed(title="An unexpected error has occurred.", color=discord.Color.red())
        LOG.exception(error)

    await interaction.response.send_message(embed=embed)


RIVER_RACE_COMMANDS = [
    predict,
    river_race_status,
]
"""Commands to be added by river_race_commands module."""
