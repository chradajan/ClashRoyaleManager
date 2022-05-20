"""Various utility functions for Discord related needs."""

import discord

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
