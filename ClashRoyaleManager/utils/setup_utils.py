"""Utility functions that interface with database for first time setup."""

from typing import List, Union

import discord

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from utils.custom_types import (
    ClanRole,
    SpecialChannel,
    SpecialRole,
    StrikeType
)

def set_clan_role(clan_role: ClanRole, discord_role: discord.Role):
    """Associate a clan role with a Discord role.

    Args:
        clan_role: Clan role to assign Discord role to.
        discord_role: Discord role to assign to clan role.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("INSERT INTO clan_role_discord_roles VALUES (DEFAULT, %s, %s) ON DUPLICATE KEY UPDATE discord_role_id = %s",
                   (clan_role.value, discord_role.id, discord_role.id))
    database.commit()
    database.close()


def set_special_role(special_role: SpecialRole, discord_role: discord.Role):
    """Associate a special role with a Discord role.

    Args:
        special_role: Special role to assign Discord role to.
        discord_role: Discord role to assign to special role.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("INSERT INTO special_discord_roles VALUES (DEFAULT, %s, %s) ON DUPLICATE KEY UPDATE discord_role_id = %s",
                   (special_role.value, discord_role.id, discord_role.id))
    database.commit()
    database.close()


def set_special_channel(special_channel: SpecialChannel, discord_channel: discord.TextChannel):
    """Save channels for automated strikes and reminders.

    Args:
        special_channel: Special channel type.
        discord_channel: Channel to send messages to.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("INSERT INTO special_discord_channels VALUES (DEFAULT, %s, %s) ON DUPLICATE KEY UPDATE discord_channel_id = %s",
                   (special_channel.value, discord_channel.id, discord_channel.id))
    database.commit()
    database.close()


def set_primary_clan(tag: str,
                     role: discord.Role,
                     track_stats: bool,
                     send_reminders: bool,
                     assign_strikes: bool,
                     strike_type: StrikeType,
                     strike_threshold: int) -> str:
    """Designate the specified clan as a primary clan.

    Args:
        tag: Tag of primary clan.
        role: Discord role given to members of this clan.
        track_stats: Whether to track deck usage and Battle Day stats for members of this clan.
        send_reminders: Whether to send automated reminders to members of this clan.
        assign_strikes: Whether to assign automated strikes to members of this clan.
        strike_type: Whether to assign strikes based on deck usage or medal counts.
        strike_threshold: How many decks are needed per day or how many medals are needed in total.

    Returns:
        Name of clan that was designated as a primary clan.

    Raises:
        GeneralAPIError: Clan does not already exist in clans table and an error was encountered getting its name from the API.
        ResourceNotFound: Clan does not already exist in clans table and is an invalid clan tag.
    """
    name = clash_utils.get_clan_name(tag)
    database, cursor = db_utils.get_database_connection()
    cursor.execute("INSERT INTO clans (tag, name, discord_role_id) VALUES (%s, %s, %s)\
                    ON DUPLICATE KEY UPDATE name = %s, discord_role_id = %s",
                   (tag, name, role.id, name, role.id))
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    clan_id = cursor.fetchone()["id"]
    args_dict = {
        "clan_id": clan_id,
        "track_stats": track_stats,
        "send_reminders": send_reminders,
        "assign_strikes": assign_strikes,
        "strike_type": strike_type.value,
        "strike_threshold": strike_threshold
    }
    cursor.execute("INSERT INTO primary_clans VALUES\
                    (%(clan_id)s, %(track_stats)s, %(send_reminders)s, %(assign_strikes)s, %(strike_type)s, %(strike_threshold)s)\
                    ON DUPLICATE KEY UPDATE track_stats = %(track_stats)s, send_reminders = %(send_reminders)s,\
                    assign_strikes = %(assign_strikes)s, strike_type = %(strike_type)s, strike_threshold = %(strike_threshold)s",
                    args_dict)
    cursor.execute("SELECT name FROM clans WHERE id = %s", (clan_id))
    name = cursor.fetchone()["name"]
    database.commit()
    database.close()
    return name


def remove_primary_clan(tag: str) -> Union[str, None]:
    """Remove the specified clan from the primary clans table.

    Args:
        tag: Tag of clan to be removed.

    Returns:
        Name of clan that was removed, or None if it was not a primary clan.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT id, name FROM clans WHERE tag = %s", (tag))
    query_result = cursor.fetchone()
    name = None

    if query_result is not None:
        clan_id = query_result["id"]
        name = query_result["name"]
        cursor.execute("DELETE FROM primary_clans WHERE clan_id = %s", (clan_id))
        database.commit()

    database.close()
    return name


def get_unset_clan_roles() -> List[ClanRole]:
    """Get a list of any clan roles that do not have an assigned Discord role.

    Returns:
        List of any clan roles that still need to be set. Empty list indicates that everything is set.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT role FROM clan_role_discord_roles")
    query_result = cursor.fetchall()
    database.close()
    set_roles = {ClanRole(role["role"]) for role in query_result}
    unset_roles = [role for role in ClanRole if role not in set_roles]
    return unset_roles


def get_unset_special_roles() -> List[SpecialRole]:
    """Get a list of any special roles that do not have an assigned Discord role.

    Returns:
        List of any special roles that still need to be set. Empty list indicates that everything is set.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT role FROM special_discord_roles")
    query_result = cursor.fetchall()
    database.close()
    set_roles = {SpecialRole(role["role"]) for role in query_result}
    unset_roles = [role for role in SpecialRole if role not in set_roles]
    return unset_roles


def get_unset_special_channels() -> List[SpecialChannel]:
    """Get a list of any unset special channels.

    Returns:
        List of any special channels that still need to be set. Empty list indicates that everything is set.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT channel FROM special_discord_channels")
    query_result = cursor.fetchall()
    database.close()
    set_channels = {SpecialChannel(channel["channel"]) for channel in query_result}
    unset_channels = [channel for channel in SpecialChannel if channel not in set_channels]
    return unset_channels


def is_primary_clan_set() -> bool:
    """Check that at least one primary clan is set.

    Returns:
        Whether at least one primary clan is set.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT clan_id FROM primary_clans")
    query_result = cursor.fetchone()
    database.close()
    return query_result is not None


def finish_setup():
    """Create season entry and create River Race data for all primary clans.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("INSERT INTO seasons VALUES (DEFAULT, DEFAULT)")
    database.commit()

    for clan in db_utils.get_primary_clans():
        db_utils.prepare_for_river_race(clan["tag"], True)
        db_utils.update_river_race_clans(clan["tag"])

    cursor.execute("UPDATE variables SET initialized = TRUE")
    database.commit()
    database.close()
