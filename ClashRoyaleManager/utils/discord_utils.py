"""Various utility functions for Discord related needs."""

from typing import List, Optional, Tuple, Union

import discord
from prettytable import PrettyTable

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from log.logger import LOG, log_message
from utils.custom_types import ReminderTime, SpecialChannel, SpecialRole
from utils.exceptions import GeneralAPIError
from utils.channel_manager import CHANNEL
from utils.role_manager import ROLE

def full_discord_name(member: discord.Member) -> str:
    """Get the full username of a Discord member. This includes username and discriminator.

    Args:
        member: Member to get full name of.

    Returns:
        Specified member's full name.
    """
    return member.name + '#' + member.discriminator


async def assign_roles(member: discord.Member):
    """Assign proper roles to user based on their clan affiliation and clan role. Should not be used for a member with the New role.

    Args:
        member: Member to fix roles of.
    """
    clan_affiliation = db_utils.get_clan_affiliation(member)

    if clan_affiliation is None:
        correct_roles = {ROLE[SpecialRole.Visitor]}
    else:
        clan_tag, in_primary_clan, clan_role = clan_affiliation
        if in_primary_clan:
            correct_roles = {
                ROLE.get_affiliated_clan_role(clan_tag),
                ROLE[clan_role]
            }
        else:
            correct_roles = {ROLE[SpecialRole.Visitor]}

    current_roles = set(member.roles).intersection(ROLE.get_all_roles())

    if current_roles != correct_roles:
        LOG.debug(log_message("Updating roles",
                              member=member,
                              current_roles=[role.name for role in current_roles],
                              correct_roles=[role.name for role in correct_roles]))
        await member.remove_roles(*list(current_roles - correct_roles))
        await member.add_roles(*list(correct_roles))


async def reset_to_new(member: discord.Member):
    """Remove a user's roles and assign them the New role.

    Args:
        member: Member to reset.
    """
    LOG.info(log_message("Removing roles and assigning new role", member=member))
    await member.remove_roles(*list(ROLE.get_all_roles()))
    await member.add_roles(ROLE[SpecialRole.New])


async def update_member(member: discord.Member, perform_database_update: bool) -> bool:
    """Update a member of the Discord server.

    Args:
        member: Member to update.
        perform_database_update: Whether user needs to be updated in database.

    Raises:
        GeneralAPIError: perform_database_update is True and something went wrong getting data from API.
    """
    LOG.info(log_message("Updating member", member=member, perform_database_update=perform_database_update))

    if perform_database_update:
        member_info = db_utils.get_user_in_database(member.id)

        if len(member_info) != 1:
            LOG.debug(log_message("Member was not found in database", member_info=member_info))
            return False

        tag, _, _ = member_info[0]
        db_utils.update_user(tag)

    name = db_utils.clear_update_flag(member.id)

    if name is None:
        return False

    if name != member.display_name:
        try:
            LOG.debug("Updating display name")
            await member.edit(nick=name)
        except discord.errors.Forbidden:
            LOG.debug("Unable to edit display name")

    await assign_roles(member)
    return True


async def update_all_members(guild: discord.Guild):
    """Update any Discord members that have changed their Discord username or were updated by the database clean up routine.

    Args:
        guild: Update members in this guild.
    """
    LOG.info("Starting update on all Discord members")
    discord_users = db_utils.get_all_discord_users()

    for member in guild.members:
        if member.bot or member.id not in discord_users:
            continue

        if full_discord_name(member) != discord_users[member.id]:
            LOG.info("Updating member due to updated Discord username")

            try:
                await update_member(member, True)
            except GeneralAPIError:
                continue

    db_utils.clean_up_database()
    members_to_update = db_utils.get_all_updated_discord_users()

    for discord_id in members_to_update:
        LOG.info("Updating member due to database clean up flag")
        member = guild.get_member(discord_id)
        await update_member(member, False)


async def send_reminder(tag: str, reminder_time: ReminderTime):
    """Send a reminder to the Reminders channel tagging users that have remaining decks.

    Args:
        tag: Tag of clan to send reminder to.
        reminder_time: Only include people in reminder in the specified reminder time.

    Raises:
        GeneralAPIError: Unable to get decks report.
    """
    decks_report = clash_utils.get_decks_report(tag)
    preferred_reminder_times = db_utils.get_user_reminder_times(reminder_time)
    channel = CHANNEL[SpecialChannel.Reminders]
    clan_name = db_utils.get_clan_name(tag)
    users_to_remind = ""
    headers = [
        "",
        "__**1 deck remaining**__",
        "__**2 decks remaining**__",
        "__**3 decks remaining**__",
        "__**4 decks remaining**__"
    ]
    current_header = headers[0]

    for player_tag, player_name, decks_remaining in decks_report["active_members_with_remaining_decks"]:
        if current_header != headers[decks_remaining]:
            current_header = headers[decks_remaining]
            users_to_remind += "\n" + current_header + "\n"

        member = None

        if player_tag in preferred_reminder_times:
            member = discord.utils.get(channel.members, id=preferred_reminder_times[player_tag])

        if member is None:
            users_to_remind += f"{discord.utils.escape_markdown(player_name)}\n"
        else:
            users_to_remind += f"{member.mention}\n"

    if users_to_remind:
        message = f"**The following members of {discord.utils.escape_markdown(clan_name)} still have decks left to use today:**\n"
        message += users_to_remind
    else:
        message = f"**All members of {discord.utils.escape_markdown(clan_name)} have already used all their decks today.**"

    await channel.send(message)


def duplicate_names_embed(users: List[Tuple[str, str, str]]) -> discord.Embed:
    """Create an embed listing out users with identical names.

    Args:
        users: List of users' tags, names, and clan names that have the same player name.

    Returns:
        Embed listing out users and info about how to proceed.
    """
    embed = discord.Embed(title="Duplicate names detected", color=discord.Color.yellow())
    embed.add_field(name="Which user did you mean?",
                    value=f"Try reissuing the command with the user's tag instead of their name.",
                    inline=False)

    for tag, name, clan_name in users:
        embed.add_field(name=f"{name}",
                        value=f"```Tag: {tag}\nClan: {clan_name}```",
                        inline=False)

    return embed


def user_not_found_embed(name: str) -> discord.Embed:
    """Create an embed explaining that the specified user does not exist in the database.

    Args:
        name: Name of user that was searched for.

    Returns:
        Embed stating the user could not be found.
    """
    embed = discord.Embed(title="User does not exist in database",
                          description=(f"No user named {discord.utils.escape_markdown(name)} was found in the database. "
                                       "If they are on Discord, make sure they've used the `/register` command."),
                          color=discord.Color.red())
    return embed


def issuer_not_registered_embed() -> discord.Embed:
    """Create an embed for when a member illegally issues a command before registering.

    Returns:
        Embed explaining the problem.
    """
    embed = discord.Embed(title="You are not registered",
                          description="You must use the `/register` command before trying to issue other commands.",
                          color=discord.Color.red())
    return embed


def get_member_from_mention(interaction: discord.Interaction, mention: str) -> Union[discord.Member, None]:
    """Get a Discord member from their mention string.
    
    Args:
        interaction: Interaction to get guild members from.
        mention: String form of a mention of a user.
    
    Returns:
        Member if a member exists, otherwise None.
    """
    member = None

    if mention.endswith(">"):
        if mention.startswith("<@!"):
            try:
                id = int(mention[3:-1])
                member = discord.utils.get(interaction.guild.members, id=id)
            except ValueError:
                pass
        elif mention.startswith("<@"):
            try:
                id = int(mention[2:-1])
                member = discord.utils.get(interaction.guild.members, id=id)
            except ValueError:
                pass

    return member


async def update_strikes_helper(search_key: Union[int, str], name: str, delta: int) -> discord.Embed:
    """Update a user's strike count and send a message to the strikes channel confirming the change.

    Args:
        search_key: Either the Discord ID or tag of the user to strike.
        name: Name of user to update strikes of.

    Returns:
        Embed confirming the update.
    """
    prev, curr = db_utils.update_strikes(search_key, delta)

    if prev is None:
        return user_not_found_embed(name)

    title = "has received a strike" if delta > 0 else "has had a strike removed"
    embed = discord.Embed(title=f"{discord.utils.escape_markdown(name)} {title}", description=f"{prev} -> {curr}")
    member = None
    message = None

    if isinstance(search_key, int):
        member = discord.utils.get(CHANNEL[SpecialChannel.Strikes].members, id=search_key)

        if member is not None:
            message = f"{member.mention}"

    await CHANNEL[SpecialChannel.Strikes].send(content=message, embed=embed)
    return embed


def get_player_report(tag: str, card_levels: bool) -> discord.Embed:
    """Get an embed with information about a player.

    Args:
        tag: Tag of user to get report of.
        card_levels: Whether to include card levels.

    Returns:
        Embed containing player report.

    Raises:
        GeneralAPIError: Unable to get data of user.
    """
    clash_data = clash_utils.get_clash_royale_user_data(tag)
    database_data = db_utils.get_player_report_data(tag)

    table = PrettyTable()
    table.add_row(["Username", clash_data["name"]])
    table.add_row(["Tag", clash_data["tag"]])

    if database_data["discord_name"] is None:
        database_data["discord_name"] = "N/A"

    table.add_row(["Discord Name", database_data["discord_name"]])
    table.add_row(["Strikes", database_data["strikes"]])
    table.add_row(["Kicks", database_data["kicks"]])

    if database_data["last_kicked"] is None:
        last_kicked = "Never"
    else:
        last_kicked = database_data["last_kicked"].strftime("%Y-%m-%d")

    table.add_row(["Last Kicked", last_kicked])

    if clash_data["clan_name"] is None:
        clash_data["clan_name"] = "N/A"
        clash_data["clan_tag"] = "N/A"
        clash_data["role"] = "N/A"
    else:
        clash_data["role"] = clash_data["role"].name

    table.add_row(["Clan", clash_data["clan_name"]])
    table.add_row(["Clan Tag", clash_data["clan_tag"]])
    table.add_row(["Clan Role", clash_data["role"]])

    embed = discord.Embed(title=f"{discord.utils.escape_markdown(clash_data['name'])} Report",
                          url=clash_utils.royale_api_url(tag),
                          description=f"```\n{table.get_string(header=False)}```")

    if card_levels:
        embed.add_field(name="Stats",
                        value=("```"
                               f"Level: {clash_data['exp_level']}\n"
                               f"Trophies: {clash_data['trophies']}\n"
                               f"Best Trophies: {clash_data['best_trophies']}\n"
                               f"Cards Owned: {clash_data['found_cards']}/{clash_data['total_cards']}"
                               "```"),
                        inline=False)

        found_cards = clash_data["found_cards"]
        card_level_string = ""
        percentile = 0

        for i in range(14, 0, -1):
            percentile += clash_data["cards"][i] / found_cards
            percentage = round(percentile * 100)

            if 0 < percentage < 5:
                card_level_string += f"{i:02d}: {'▪':<20}  {percentage:02d}%\n"
            else:
                card_level_string += f"{i:02d}: {(percentage // 5) * '■':<20}  {percentage:02d}%\n"

            if percentage == 100:
                break

        embed.add_field(name="Card Levels", value=f"```{card_level_string}```", inline=False)

    return embed


def get_stats_report(player_tag: str,
                     player_name: str,
                     clan_tag: Optional[str]=None,
                     clan_name: Optional[str]=None) -> discord.Embed:
    """Create an embed displaying a user's stats.

    Args:
        player_tag: Tag of user to get stats of.
        player_name: Name of user to get stats of.
        clan_tag: Get stats of user in this clan. If None, get stats from all clans.
        clan_name: Name of clan to get stats in.

    Returns:
        Embed of stats.
    """
    stats = db_utils.get_stats(player_tag, clan_tag)
    clan_name = discord.utils.escape_markdown(clan_name) if clan_name is not None else "all clans"
    title = f"{discord.utils.escape_markdown(player_name)}'s stats in {clan_name}"
    embed = discord.Embed(title=title, color=discord.Color.random())
    combined_wins = 0
    combined_losses = 0

    # Regular matches
    wins = stats["regular_wins"]
    losses = stats["regular_losses"]
    combined_wins += wins
    combined_losses += losses
    total = wins + losses
    win_rate = "0.00%" if total == 0 else f"{wins / total:.2%}"
    embed.add_field(name="Regular PvP",
                    value=f"```Wins   {wins}\nLosses {losses}\nTotal:  {total}\nWin Rate: {win_rate}```")

    # Special matches
    wins = stats["special_wins"]
    losses = stats["special_losses"]
    combined_wins += wins
    combined_losses += losses
    total = wins + losses
    win_rate = "0.00%" if total == 0 else f"{wins / total:.2%}"
    embed.add_field(name="Special PvP",
                    value=f"```Wins   {wins}\nLosses {losses}\nTotal:  {total}\nWin Rate: {win_rate}```")

    # Divider
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # Duel matches
    wins = stats["duel_wins"]
    losses = stats["duel_losses"]
    combined_wins += wins
    combined_losses += losses
    total = wins + losses
    win_rate = "0.00%" if total == 0 else f"{wins / total:.2%}"
    embed.add_field(name="Duel (matches)",
                    value=f"```Wins   {wins}\nLosses {losses}\nTotal:  {total}\nWin Rate: {win_rate}```")

    # Duel series
    wins = stats["series_wins"]
    losses = stats["series_losses"]
    total = wins + losses
    win_rate = "0.00%" if total == 0 else f"{wins / total:.2%}"
    embed.add_field(name="Duel (series)",
                    value=f"```Wins   {wins}\nLosses {losses}\nTotal:  {total}\nWin Rate: {win_rate}```")

    # Divider
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # Combined matches
    total = combined_wins + combined_losses
    win_rate = "0.00%" if total == 0 else f"{combined_wins / total:.2%}"
    embed.add_field(name="Combined PvP",
                    value=f"```Wins   {combined_wins}\nLosses {combined_losses}\nTotal:  {total}\nWin Rate: {win_rate}```",
                    inline=False)

    # Boat attacks
    wins = stats["boat_wins"]
    losses = stats["boat_losses"]
    total = wins + losses
    win_rate = "0.00%" if total == 0 else f"{wins / total:.2%}"
    embed.add_field(name="Boat Attacks",
                    value=f"```Wins   {wins}\nLosses {losses}\nTotal:  {total}\nWin Rate: {win_rate}```")

    return embed
