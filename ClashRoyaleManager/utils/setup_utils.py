"""Utility functions that interface with database for first time setup."""

from typing import List, Union

import discord

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from utils.custom_types import (
    ClanRole,
    SpecialRole,
    StrikeCriteria
)

def set_clan_role(clan_role: ClanRole, discord_role: discord.Role) -> Union[int, None]:
    """Associate a clan role with a Discord role.

    Args:
        clan_role: Clan role to assign Discord role to.
        discord_role: Discord role to assign to clan role.

    Returns:
        ID of previously associated Discord role if there was one, else None.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT discord_role_id FROM clan_role_discord_roles WHERE role = %s", (clan_role.value))
    query_result = cursor.fetchone()

    if query_result is None:
        cursor.execute("INSERT INTO clan_role_discord_roles VALUES (DEFAULT, %s, %s)", (clan_role.value, discord_role.id))
        former_id = None
    else:
        cursor.execute("UPDATE clan_role_discord_roles SET discord_role_id = %s WHERE role = %s",
                       (discord_role.id, clan_role.value))
        former_id = query_result["discord_role_id"]

    database.commit()
    database.close()
    return former_id


def set_special_role(special_role: SpecialRole, discord_role: discord.Role) -> Union[int, None]:
    """Associate a special role with a Discord role.

    Args:
        special_role: Special role to assign Discord role to.
        discord_role: Discord role to assign to special role.

    Returns:
        ID of previously associated Discord role if there was one, else None.
    """
    database, cursor = db_utils.get_database_connection()
    cursor.execute("SELECT discord_role_id FROM special_discord_roles WHERE role = %s", (special_role.value))
    query_result = cursor.fetchone()

    if query_result is None:
        cursor.execute("INSERT INTO special_discord_roles VALUES (DEFAULT, %s, %s)", (special_role.value, discord_role.id))
        former_id = None
    else:
        cursor.execute("UPDATE special_discord_roles SET discord_role_id = %s WHERE role = %s",
                       (discord_role.id, special_role.value))
        former_id = query_result["discord_role_id"]

    database.commit()
    database.close()
    return former_id


def set_primary_clan(tag: str,
                     role: discord.Role,
                     track_stats: bool,
                     send_reminders: bool,
                     assign_strikes: bool,
                     strike_type: StrikeCriteria,
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
    clan_id = db_utils.insert_clan(tag=tag, discord_role_id=role.id)
    args_dict = {
        "clan_id": clan_id,
        "track_stats": track_stats,
        "send_reminders": send_reminders,
        "assign_strikes": assign_strikes,
        "strike_type": strike_type.value,
        "strike_threshold": strike_threshold
    }
    database, cursor = db_utils.get_database_connection()
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
    cursor.execute("SELECT MAX(id) AS id FROM seasons")
    season_id = cursor.fetchone()["id"]
    primary_clans = db_utils.get_primary_clans()

    for clan in primary_clans:
        try:
            river_race_info = clash_utils.get_current_river_race_info(clan["tag"])
        except Exception as e:
            database.close()
            raise e

        river_race_info["clan_id"] = clan["id"]
        river_race_info["season_id"] = season_id
        cursor.execute("INSERT INTO river_races (clan_id, season_id, start_time, colosseum_week, completed_saturday, week)\
                        VALUES (%(clan_id)s, %(season_id)s, %(start_time)s, %(colosseum_week)s, %(completed_saturday)s, %(week)s)",
                       river_race_info)

        for tag, name in river_race_info["clans"]:
            cursor.execute("INSERT INTO river_race_clans (season_id, tag, name) VALUES (%s, %s, %s)", (season_id, tag, name))
            cursor.execute("INSERT INTO clans_in_race VALUES\
                            ((SELECT MAX(id) FROM river_races), (SELECT MAX(id) FROM river_race_clans))")

    cursor.execute("UPDATE variables SET initialized = TRUE")
    database.commit()
    database.close()
