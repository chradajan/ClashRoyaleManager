"""Status report commands."""

import discord
from discord import app_commands
from prettytable import PrettyTable

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
from log.logger import LOG
from utils.exceptions import GeneralAPIError

PRIMARY_CLANS = db_utils.get_primary_clans_enum()

@app_commands.command()
@app_commands.describe(clan="Which clan to get a report for")
async def decks_report(interaction: discord.Interaction, clan: PRIMARY_CLANS):
    """Get a report of players with decks left to use today."""
    LOG.command_start(interaction, clan=clan)
    report = clash_utils.get_decks_report(clan.value)
    description_text = (f"{report['participants']} players have participated in the River Race today and have used a total of "
                        f"{200 - report['remaining_decks']} decks.")

    headers = [
            "__**0 decks remaining**__",
            "__**1 deck remaining**__",
            "__**2 decks remaining**__",
            "__**3 decks remaining**__",
            "__**4 decks remaining**__"
        ]

    if report["active_members_with_remaining_decks"]:
        description_text += " The following members of the clan still have decks left to use today:\n"
        current_header = headers[0]

        for _, name, decks_remaining in report["active_members_with_remaining_decks"]:
            if current_header != headers[decks_remaining]:
                current_header = headers[decks_remaining]
                description_text += "\n" + current_header + "\n"

            description_text += f"{discord.utils.escape_markdown(name)}\n"
    else:
        description_text += " There are currently no members in the clan with decks left to use today."

    embed = discord.Embed(title=f"{discord.utils.escape_markdown(clan.name)} Decks Report",
                          description=description_text)

    if report["inactive_members_with_decks_used"]:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        current_header = headers[report["inactive_members_with_decks_used"][0][2]]
        value_text = "\n" + current_header + "\n"

        for _, name, decks_remaining in report["inactive_members_with_decks_used"]:
            if current_header != headers[decks_remaining]:
                current_header = headers[decks_remaining]
                value_text += "\n" + current_header + "\n"

            value_text += f"{discord.utils.escape_markdown(name)}\n"

        embed.add_field(name="The following players participated today but are not currently active members of the clan:",
                        value=value_text,
                        inline=True)

    if report["locked_out_active_members"]:
        value_text = ""

        for _, name, _ in report["locked_out_active_members"]:
            value_text += f"{discord.utils.escape_markdown(name)}\n"

        embed.add_field(name=("The following players are active members of the clan that are locked out of battling today due to "
                              "the 50 participant cap:"),
                        value=value_text,
                        inline=True)

    remaining_participants = 50 - report["participants"]
    non_battling_active_members = report["active_members_with_no_decks_used"]

    if non_battling_active_members > remaining_participants:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="WARNING",
                        value=(f"Only {remaining_participants} players can still battle today before hitting the 50 participant "
                               f"cap. There are currently {non_battling_active_members} active members of the clan that have not "
                               "used any decks today. Some players could be locked out of battling today."),
                        inline=False)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(clan="Which clan to get a report for")
@app_commands.describe(threshold="Show members with fewer medals than this")
async def medals_report(interaction: discord.Interaction, clan: PRIMARY_CLANS, threshold: app_commands.Range[int, 0, 3600]):
    """Get a list of players below a specified number of medals."""
    LOG.command_start(interaction, clan=clan, threshold=threshold)
    members = clash_utils.medals_report(clan.value, threshold)
    table = PrettyTable()
    table.field_names = ["Member", "Medals"]

    for name, medals in members:
        table.add_row([discord.utils.escape_markdown(name), medals])

    embed = discord.Embed(title=f"{discord.utils.escape_markdown(clan.name)} Medals Report",
                          description=f"```\n{table.get_string()}```")
    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(user="User to get a report on")
@app_commands.describe(show_card_levels="Whether to include information about the specified user's card levels")
async def player_report(interaction: discord.Interaction, user: str, show_card_levels: bool=False):
    """Get more information about a user."""
    LOG.command_start(interaction, user=user)
    member = discord_utils.get_member_from_mention(interaction, user)

    if member is not None:
        search_results = db_utils.get_user_in_database(member.id)
    else:
        search_results = db_utils.get_user_in_database(user)

    if not search_results:
        embed = discord_utils.user_not_found_embed(user)
    elif len(search_results) > 1:
        embed = discord_utils.duplicate_names_embed(search_results)
    else:
        tag, _, _ = search_results[0]
        embed = discord_utils.get_player_report(tag, show_card_levels)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(user="User to get stats of")
@app_commands.describe(clan="Get stats of user in this clan, or combined across all clans if not specified")
async def stats_report(interaction: discord.Interaction, user: str, clan: PRIMARY_CLANS=None):
    """Get a user's Battle Day stats."""
    LOG.command_start(interaction, user=user, clan=clan)
    member = discord_utils.get_member_from_mention(interaction, user)

    if member is not None:
        search_results = db_utils.get_user_in_database(member.id)
    else:
        search_results = db_utils.get_user_in_database(user)

    if not search_results:
        embed = discord_utils.user_not_found_embed(user)
    elif len(search_results) > 1:
        embed = discord_utils.duplicate_names_embed(search_results)
    else:
        player_tag, player_name, _ = search_results[0]
        clan_tag = None
        clan_name = None

        if clan is not None:
            clan_tag = clan.value
            clan_name = clan.name

        embed = discord_utils.get_stats_report(player_tag, player_name, clan_tag, clan_name)

    await interaction.response.send_message(embed=embed)
    LOG.command_end()


@app_commands.command()
@app_commands.describe(private="Whether to display your stats privately (True) or publicly send to current channel (False)")
@app_commands.describe(clan="Get your stats in this clan, or combined across all clans if not specified")
async def stats(interaction: discord.Interaction, private: bool, clan: PRIMARY_CLANS=None):
    """Check your Battle Day stats."""
    LOG.command_start(interaction, private=private, clan=clan)
    search_results = db_utils.get_user_in_database(interaction.user.id)

    if not search_results:
        embed = discord_utils.issuer_not_registered_embed()
    else:
        player_tag, player_name, _ = search_results[0]
        clan_tag = None
        clan_name = None

        if clan is not None:
            clan_tag = clan.value
            clan_name = clan.name

        embed = discord_utils.get_stats_report(player_tag, player_name, clan_tag, clan_name)

    await interaction.response.send_message(embed=embed, ephemeral=private)
    LOG.command_end()


@decks_report.error
@medals_report.error
@player_report.error
@stats_report.error
@stats.error
async def status_report_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for status report commands."""
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


STATUS_REPORT_COMMANDS = [
    decks_report,
    medals_report,
    player_report,
    stats_report,
    stats,
]
"""Commands to be added by status_reports module."""
