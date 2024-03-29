"""Functions that interface with the database."""

import datetime
import os
import requests
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

import discord
import pymysql
import xlsxwriter
from pymysql.cursors import DictCursor
from xlsxwriter.worksheet import Worksheet

import utils.clash_utils as clash_utils
import utils.discord_utils as discord_utils
from config.credentials import (
    IP,
    USERNAME,
    PASSWORD,
    DATABASE_NAME
)
from log.logger import LOG, log_message
from utils.custom_types import (
    AutomatedRoutine,
    Battles,
    BattleStats,
    BoatBattle,
    Card,
    ClanRole,
    ClanStrikeInfo,
    ClashData,
    DatabaseReport,
    DatabaseRiverRaceClan,
    Duel,
    KickData,
    PrimaryClan,
    PvPBattle,
    ReminderTime,
    RiverRaceUserData,
    SpecialChannel,
    SpecialRole,
)
from utils.exceptions import GeneralAPIError, ResourceNotFound
from utils.outside_battles_queue import UNSENT_WARNINGS

EXPORT_PATH = "export_data"
CARD_IMAGE_PATH = "card_images"

def get_database_connection() -> Tuple[pymysql.Connection, DictCursor]:
    """Establish connection to database.

    Returns:
        Database connection and cursor.
    """
    database = pymysql.connect(host=IP, user=USERNAME, password=PASSWORD, database=DATABASE_NAME, charset='utf8mb4')
    cursor = database.cursor(pymysql.cursors.DictCursor)
    return (database, cursor)


###################################################################################################################
#    _   _                 ___                     _   _                ___   _           _       _               #
#   | | | |___  ___ _ __  |_ _|_ __  ___  ___ _ __| |_(_) ___  _ __    / / | | |_ __   __| | __ _| |_ ___  ___    #
#   | | | / __|/ _ \ '__|  | || '_ \/ __|/ _ \ '__| __| |/ _ \| '_ \  / /| | | | '_ \ / _` |/ _` | __/ _ \/ __|   #
#   | |_| \__ \  __/ |     | || | | \__ \  __/ |  | |_| | (_) | | | |/ / | |_| | |_) | (_| | (_| | ||  __/\__ \   #
#    \___/|___/\___|_|    |___|_| |_|___/\___|_|   \__|_|\___/|_| |_/_/   \___/| .__/ \__,_|\__,_|\__\___||___/   #
#                                                                              |_|                                #
###################################################################################################################

def insert_clan(tag: str, name: str, cursor: Optional[pymysql.cursors.DictCursor]=None) -> int:
    """Insert a new clan into the clans table. Update its name if it already exists.

    Args:
        tag: Tag of clan to insert.
        name: Name of clan to insert.
        cursor: Cursor used to interact with database. If not provided, will create a new one. Otherwise, use the one provided.
                Caller is responsible for committing changes made by cursor if provided.

    Returns:
        ID of clan being inserted.
    """
    close_connection = False

    if cursor is None:
        close_connection = True
        database, cursor = get_database_connection()

    cursor.execute("INSERT INTO clans (tag, name, discord_role_id) VALUES (%s, %s, %s)\
                    ON DUPLICATE KEY UPDATE name = %s",
                   (tag, name, get_special_role_id(SpecialRole.Visitor), name))
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    id = cursor.fetchone()["id"]

    if close_connection:
        database.commit()
        database.close()

    return id


def update_clan_affiliation(clash_data: ClashData, cursor: Optional[pymysql.cursors.DictCursor]=None):
    """Nullify role of any existing clan affiliations for the given user. Update/create a clan affiliation for their current clan.

    Args:
        clash_data: Data of user to update clan_affiliations for.
        cursor: Cursor used to interact with database. If not provided, will create a new one. Otherwise, use the one provided.
                Caller is responsible for committing changes made by cursor if provided.

    Precondition:
        clash_data must contain a key called 'user_id' corresponding to their key in the users table.
    """
    close_connection = False

    if cursor is None:
        close_connection = True
        database, cursor = get_database_connection()

    # Get ID of current affiliation if one exists.
    cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND role IS NOT NULL", clash_data)
    query_result = cursor.fetchone()

    if query_result is None:
        current_affiliation_id = None
    else:
        current_affiliation_id = query_result["id"]

    # Nullify any existing affiliations.
    cursor.execute("UPDATE clan_affiliations SET role = NULL WHERE user_id = %(user_id)s", clash_data)

    if clash_data["clan_tag"] is not None:
        # Create/update clan affiliation for user if they are in a clan.
        clash_data["clan_id"] = insert_clan(clash_data["clan_tag"], clash_data["clan_name"], cursor)
        clash_data["role_name"] = clash_data["role"].value
        cursor.execute("INSERT INTO clan_affiliations (user_id, clan_id, role) VALUES (%(user_id)s, %(clan_id)s, %(role_name)s)\
                        ON DUPLICATE KEY UPDATE role = %(role_name)s",
                       clash_data)

        # Check if user is in a primary clan and create a river_race_user_data entry if so.
        cursor.execute("SELECT clan_id FROM primary_clans WHERE clan_id = %(clan_id)s", clash_data)
        query_result = cursor.fetchone()

        if query_result is not None:
            # Create River Race user data entry for user if necessary.
            cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", clash_data)
            clash_data["clan_affiliation_id"] = cursor.fetchone()["id"]
            clash_data["river_race_id"], _, _, _ = get_clan_river_race_ids(clash_data["clan_tag"])

            if clash_data["river_race_id"] is not None:
                cursor.execute("SELECT last_check, battle_time FROM river_races WHERE id = %(river_race_id)s", clash_data)
                query_result = cursor.fetchone()
                clash_data["last_check"] = query_result["last_check"]
                is_battle_day = query_result["battle_time"]

                if is_battle_day:
                    cursor.execute("INSERT INTO river_race_user_data\
                                    (clan_affiliation_id, river_race_id, last_check, tracked_since)\
                                    VALUES (%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s, CURRENT_TIMESTAMP)\
                                    ON DUPLICATE KEY UPDATE\
                                    tracked_since = COALESCE(tracked_since, CURRENT_TIMESTAMP), last_check = last_check",
                                   clash_data)

                    # Check if user battled for another clan today and is unable to battle for their new clan.
                    last_reset_time = get_most_recent_reset_time(clash_data["clan_tag"])
                    outside_battles = 0

                    if last_reset_time is not None:
                        last_reset_time = last_reset_time.replace(hour=10, minute=0, second=0, microsecond=0)
                        try:
                            outside_battles = clash_utils.battled_for_other_clan(clash_data["tag"],
                                                                                 clash_data["clan_tag"],
                                                                                 last_reset_time)
                        except (GeneralAPIError, ResourceNotFound) as error:
                            LOG.warning("Error occurred while checking for battles in previous clans")
                            outside_battles = 0

                    if outside_battles > 0:
                        cursor.execute("SELECT day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s",
                                       (clash_data["river_race_id"]))

                        query_result = cursor.fetchone()
                        outside_battles_key = None

                        for key in ["day_4", "day_5", "day_6", "day_7"]:
                            if query_result[key] is None:
                                outside_battles_key = key
                                break

                        if outside_battles_key is not None:
                            UNSENT_WARNINGS.append((clash_data, outside_battles))
                            outside_battles_key = outside_battles_key + "_outside_battles"
                            query = (f"UPDATE river_race_user_data SET {outside_battles_key} = %s, last_check = last_check "
                                     "WHERE clan_affiliation_id = %s AND river_race_id = %s")

                            cursor.execute(query,
                                           (outside_battles,
                                            clash_data["clan_affiliation_id"],
                                            clash_data["river_race_id"]))
                else:
                    cursor.execute("INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check)\
                                    VALUES (%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s)\
                                    ON DUPLICATE KEY UPDATE clan_affiliation_id = clan_affiliation_id",
                                   clash_data)

    # If affiliation has changed, make relevant changes to clan_time table.
    new_affiliation_id = clash_data.get("clan_affiliation_id")

    if current_affiliation_id != new_affiliation_id:
        LOG.info(log_message("Updating clan times",
                             current_affiliation_id=current_affiliation_id,
                             new_affiliation_id=new_affiliation_id))

        if current_affiliation_id is not None:
            cursor.execute("UPDATE clan_time SET end = CURRENT_TIMESTAMP WHERE clan_affiliation_id = %s AND end IS NULL",
                           (current_affiliation_id))
        if new_affiliation_id is not None:
            cursor.execute("INSERT INTO clan_time (clan_affiliation_id) VALUES (%s)", (new_affiliation_id))

    if close_connection:
        database.commit()
        database.close()


def insert_new_user(clash_data: ClashData,
                    member: Optional[discord.Member]=None,
                    cursor: Optional[pymysql.cursors.DictCursor]=None) -> bool:
    """Insert a new user into the database.

    Args:
        clash_data: Clash Royale data of user to be inserted.
        member: Member object of user to be inserted if they join through the Discord server. If not provided, discord_name and
                discord_id will be left NULL.
        cursor: Cursor used to interact with database. If not provided, will create a new one. Otherwise, use the one provided.
                Caller is responsible for committing changes made by cursor if provided.

    Returns:
        True if member was inserted, False if player tag is already associated with a user on the Discord server.
    """
    close_connection = False

    if cursor is None:
        close_connection = True
        database, cursor = get_database_connection()

    if member is None:
        clash_data["discord_id"] = None
        clash_data["discord_name"] = None
    else:
        clash_data["discord_id"] = member.id
        clash_data["discord_name"] = discord_utils.full_discord_name(member)

    cursor.execute("SELECT id, discord_id FROM users WHERE tag = %(tag)s", clash_data)
    query_result = cursor.fetchone()

    if query_result is None:
        cursor.execute("INSERT INTO users (discord_id, discord_name, tag, name)\
                        VALUES (%(discord_id)s, %(discord_name)s, %(tag)s, %(name)s)",
                       clash_data)
        cursor.execute("SELECT id FROM users WHERE tag = %(tag)s", clash_data)
        clash_data["user_id"] = cursor.fetchone()["id"]
    else:
        clash_data["user_id"] = query_result["id"]

        if query_result["discord_id"] is None:
            cursor.execute("UPDATE users SET discord_id = %(discord_id)s, discord_name = %(discord_name)s, name = %(name)s\
                            WHERE id = %(user_id)s",
                           clash_data)
        else:
            if close_connection:
                database.close()
            return False

    update_clan_affiliation(clash_data, cursor)

    if close_connection:
        database.commit()
        database.close()

    return True


def update_user(tag: str, discord_name: Optional[str]=None):
    """Get a user's most up to date information and update their name and clan affiliation.

    Args:
        tag: Tag of user to update.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag or the tag of a banned user was provided.
    """
    LOG.info(f"Updating user with tag {tag}")
    clash_data = clash_utils.get_clash_royale_user_data(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM users WHERE tag = %(tag)s", clash_data)
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return
    else:
        clash_data["user_id"] = query_result["id"]

    if discord_name is not None:
        clash_data["discord_name"] = discord_name
        cursor.execute("UPDATE users SET name = %(name)s, discord_name = %(discord_name)s, needs_update = TRUE\
                        WHERE id = %(user_id)s",
                       clash_data)
    else:
        cursor.execute("UPDATE users SET name = %(name)s, needs_update = TRUE WHERE id = %(user_id)s", clash_data)

    database.commit()
    database.close()
    update_clan_affiliation(clash_data)


def update_banned_user(tag: str):
    """Remove any clan affiliations of a user that has been banned by SuperCell.

    Args:
        tag: Player tag of user to update.
    """
    LOG.info(f"Updating banned user with tag {tag}")
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM users WHERE tag = %s", (tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return

    user_id = query_result["id"]
    cursor.execute("UPDATE users SET needs_update = FALSE WHERE id = %s", (user_id))
    clash_data = {"user_id": user_id, "clan_tag": None}

    update_clan_affiliation(clash_data, cursor)

    database.commit()
    database.close()


def dissociate_discord_info_from_user(member: discord.Member):
    """Clear discord_id and discord_name from a user when they leave the server.

    Args:
        member: Discord member that just left the server.
    """
    database, cursor = get_database_connection()
    cursor.execute("UPDATE users SET discord_id = NULL, discord_name = NULL WHERE discord_id = %s", (member.id))
    database.commit()
    database.close()


def get_all_updated_discord_users() -> Set[int]:
    """Get set of all Discord users that need to be updated.

    Returns:
        Set of Discord IDs of users that should be updated.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_id FROM users WHERE discord_id IS NOT NULL AND needs_update = TRUE")
    database.close()
    return {user["discord_id"] for user in cursor}


def clear_update_flag(discord_id: int) -> Union[str, None]:
    """Clear the needs_update flag of the specified user and get their current in-game username.

    Args:
        discord_id: Discord ID of user to clear update flag for.

    Returns:
        Current in-game username of specified user, or None if user is not in database.
    """
    database, cursor = get_database_connection()
    cursor.execute("UPDATE users SET needs_update = FALSE WHERE discord_id = %s", (discord_id))
    cursor.execute("SELECT name FROM users WHERE discord_id = %s", (discord_id))
    query_result = cursor.fetchone()
    database.commit()
    database.close()

    if query_result is None:
        LOG.debug("User was not found in database, unable to clear needs_update flag")
        return None

    return query_result["name"]


def add_unregistered_users(tag: str):
    """Add any unregistered users from the specified clan to the database.

    Args:
        tag: Tag of clan to add users from.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    LOG.info(f"Adding any unregistered users from {tag}")
    active_members = clash_utils.get_active_members_in_clan(tag).copy()
    database, cursor = get_database_connection()
    cursor.execute("SELECT tag FROM users")
    database.close()

    for registered_user in cursor:
        active_members.pop(registered_user["tag"], None)

    for unregistered_tag in active_members:
        try:
            clash_data = clash_utils.get_clash_royale_user_data(unregistered_tag)
        except GeneralAPIError:
            LOG.warning(f"Failed to add unregistered user {unregistered_tag}")
            continue

        insert_new_user(clash_data)

    LOG.info("Finished adding unregistered users")


def clean_up_database():
    """Update the database to reflect changes to members in the primary clans.

    Updates any user that is either
        a. in a primary clan but is not affiliated with that clan
        b. in a primary clan but is not affiliated with the correct role
        c. in a primary clan but has changed their in-game username
        d. not in a primary clan but is currently affiliated with one

    Raises:
        GeneralAPIError: Something went wrong when getting active members of one of the primary clans.
    """
    LOG.info("Starting database clean up")
    primary_clans = get_primary_clans()
    clan_affiliations = get_all_clan_affiliations()
    all_primary_active_members = {}
    primary_clan_tags = set()

    for clan in primary_clans:
        primary_clan_tags.add(clan["tag"])
        clan["active_members"] = clash_utils.get_active_members_in_clan(clan["tag"])
        all_primary_active_members.update(clan["active_members"])

    for player_tag, player_name, clan_tag, clan_role in clan_affiliations:
        if player_tag in all_primary_active_members:
            if (clan_tag != all_primary_active_members[player_tag]["clan_tag"]
                    or clan_role != all_primary_active_members[player_tag]["role"]
                    or player_name != all_primary_active_members[player_tag]["name"]):
                try:
                    LOG.info("Updating user in a primary clan")
                    update_user(player_tag)
                except GeneralAPIError:
                    continue
        elif clan_tag in primary_clan_tags:
            try:
                LOG.info("Updating user formerly in a primary clan")
                update_user(player_tag)
            except GeneralAPIError:
                continue
            except ResourceNotFound:
                LOG.warning(f"{player_tag} appears to be the tag of a banned user. Removing clan affiliation.")
                update_banned_user(player_tag)
                continue

    LOG.info("Database clean up complete")


def set_reminder_time(discord_id: int, reminder_time: ReminderTime):
    """Update a user's reminder time.

    Args:
        discord_id: Discord ID of user to update.
        reminder_time: New preferred time to receive reminders.
    """
    database, cursor = get_database_connection()
    cursor.execute("UPDATE users SET reminder_time = %s WHERE discord_id = %s", (reminder_time.value, discord_id))
    database.commit()
    database.close()


###################################################
#    ____                      _                  #
#   / ___|  ___  __ _ _ __ ___| |__   ___  ___    #
#   \___ \ / _ \/ _` | '__/ __| '_ \ / _ \/ __|   #
#    ___) |  __/ (_| | | | (__| | | |  __/\__ \   #
#   |____/ \___|\__,_|_|  \___|_| |_|\___||___/   #
#                                                 #
###################################################

def get_clans_in_database() -> Dict[str, str]:
    """Get all clans saved in the database.

    Returns:
        Dictionary mapping clan tags to names.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT tag, name FROM clans")
    tags = {clan["tag"]: clan["name"] for clan in cursor}
    database.close()
    return tags


def get_user_in_database(search_key: Union[int, str]) -> List[Tuple[str, str, Union[str, None]]]:
    """Find a user(s) in the database corresponding to the search key.

    First try searching for a user where discord_id == search_key if key is an int, otherwise where player_tag == search_key. If no
    results are found, then try searching where player_name == search_key. Player names are not unique and could result in finding
    multiple users. If this occurs, all users that were found are returned.

    Args:
        search_key: Key to search for in database. Can be discord id, player tag, or player name.

    Returns:
        List of tuples of (player tag, player name, clan name).
    """
    database, cursor = get_database_connection()
    search_results = []

    if isinstance(search_key, int):
        cursor.execute("SELECT id, tag, name FROM users WHERE discord_id = %s", (search_key))
        users = cursor.fetchall()
    else:
        cursor.execute("SELECT id, tag, name FROM users WHERE tag = %s", (search_key))
        users = cursor.fetchall()

        if not users:
            cursor.execute("SELECT id, tag, name FROM users WHERE name = %s", (search_key))
            users = cursor.fetchall()

    for user in users:
        cursor.execute("SELECT clans.name AS clan_name FROM clans\
                        INNER JOIN clan_affiliations ON clans.id = clan_affiliations.clan_id\
                        INNER JOIN users ON clan_affiliations.user_id = users.id\
                        WHERE users.id = %s AND clan_affiliations.role IS NOT NULL",
                       (user["id"]))
        query_result = cursor.fetchone()

        if query_result is None:
            search_results.append((user["tag"], user["name"], None))
        else:
            search_results.append((user["tag"], user["name"], query_result["clan_name"]))

    database.close()
    return search_results


def get_primary_clans() -> List[PrimaryClan]:
    """Get all primary clans.

    Returns:
        List of primary clans.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT * FROM primary_clans INNER JOIN clans ON primary_clans.clan_id = clans.id")
    database.close()
    primary_clans: List[PrimaryClan] = []

    for clan in cursor:
        clan_data: PrimaryClan = {
            "tag": clan["tag"],
            "name": clan["name"],
            "id": clan["id"],
            "discord_role_id": clan["discord_role_id"],
            "track_stats": clan["track_stats"],
            "send_reminders": clan["send_reminders"],
            "assign_strikes": clan["assign_strikes"],
            "strike_threshold": clan["strike_threshold"],
            "discord_channel_id": clan["discord_channel_id"]
        }
        primary_clans.append(clan_data)

    return primary_clans


def get_primary_clans_enum() -> Enum:
    database, cursor = get_database_connection()
    cursor.execute("SELECT clans.tag, clans.name FROM clans INNER JOIN primary_clans ON clans.id = primary_clans.clan_id")
    query_result = cursor.fetchall()
    database.close()

    if not query_result:
        return Enum("PrimaryClan", {"COMPLETE SETUP": "COMPLETE SETUP", "INCOMPLETE": "INCOMPLETE"})
    else:
        return Enum("PrimaryClan", {clan["name"]: clan["tag"] for clan in query_result})


def get_all_discord_users() -> Dict[int, str]:
    """Get dictionary of all Discord IDs and usernames in the database.

    Returns:
        Dictionary mapping Discord ID to username.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_id, discord_name FROM users WHERE discord_id IS NOT NULL")
    database.close()
    return {user["discord_id"]: user["discord_name"] for user in cursor}


def get_clan_affiliation(member: discord.Member) -> Union[Tuple[str, bool, ClanRole], None]:
    """Get a user's clan affiliation.

    Args:
        member: Discord user to get clan affiliation for.

    Returns:
        Tuple of user's clan tag, whether they're in a primary clan, and role in that clan, or None if they are not in a clan.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT clans.tag AS tag, clans.id AS clan_id, clan_affiliations.role AS role FROM users\
                    INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                    INNER JOIN clans ON clans.id = clan_affiliations.clan_id\
                    WHERE users.discord_id = %s AND clan_affiliations.role IS NOT NULL",
                   (member.id))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return None

    cursor.execute("SELECT clan_id FROM primary_clans WHERE clan_id = %s", (query_result["clan_id"]))
    database.close()

    return (query_result["tag"], cursor.fetchone() is not None, ClanRole(query_result["role"]))


def get_all_clan_affiliations() -> List[Tuple[str, str, Union[str, None], Union[ClanRole, None]]]:
    """Get the clan affiliation of all users in the database.

    Returns:
        List of tuples of player tag, player name, clan tag, and clan role. If user is not in clan, then None is returned for clan
        tag and role.
    """
    database, cursor = get_database_connection()
    clan_affiliations = []
    cursor.execute("SELECT clans.tag AS clan_tag, users.tag AS player_tag, users.name AS name, clan_affiliations.role AS role\
                    FROM users INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                    INNER JOIN clans ON clans.id = clan_affiliations.clan_id\
                    WHERE clan_affiliations.role IS NOT NULL")

    for user in cursor:
        clan_affiliations.append((user["player_tag"], user["name"], user["clan_tag"], ClanRole(user["role"])))

    cursor.execute("SELECT tag, name FROM users WHERE id NOT IN (SELECT users.id FROM users INNER JOIN clan_affiliations ON\
                    users.id = clan_affiliations.user_id WHERE clan_affiliations.role IS NOT NULL)")

    for user in cursor:
        clan_affiliations.append((user["tag"], user["name"], None, None))

    database.close()
    return clan_affiliations


def get_clan_river_race_ids(tag: str, n: int=0) -> Tuple[int, int, int, int]:
    """Get a clan's current River Race entry id, clan_id, season_id, and week.

    Args:
        tag: Tag of clan to get IDs of.
        n: How many River races back to get IDs of. 0 is current race, 1 is previous race, etc.

    Returns:
        Tuple of id, clan_id, season_id, and week of most recent River Race entry of specified clan, or None if no entry exists.
    """
    database, cursor = get_database_connection()
    river_race = None
    cursor.execute("SELECT MAX(id) AS id FROM seasons")
    season_id = cursor.fetchone()["id"]

    while n >= 0 and season_id > 0:
        cursor.execute("SELECT id, clan_id, season_id, week FROM river_races WHERE\
                        clan_id = (SELECT id FROM clans WHERE tag = %s) AND season_id = %s",
                       (tag, season_id))
        query_result = cursor.fetchall()

        if n < len(query_result):
            query_result.sort(key=lambda x: x["week"], reverse=True)
            river_race = query_result[n]
            break
        else:
            season_id -= 1
            n -= len(query_result)
    
    database.close()

    river_race_id = None
    clan_id = None
    season_id = None
    week = None

    if river_race is not None:
        river_race_id = river_race["id"]
        clan_id = river_race["clan_id"]
        season_id = river_race["season_id"]
        week = river_race["week"]

    return (river_race_id, clan_id, season_id, week)


def get_most_recent_reset_time(tag: str) -> Union[datetime.datetime, None]:
    """Get the most recent daily reset time for the specified clan.

    Args:
        tag: Tag of clan to get latest daily reset time for.

    Returns:
        Most recent daily reset time, or None if no resets are currently logged.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT day_1, day_2, day_3, day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    reset_times = [reset_time for reset_time in query_result.values() if reset_time is not None]
    reset_times.sort()
    return reset_times[-1] if reset_times else None


def get_user_reminder_times(reminder_time: ReminderTime) -> Dict[str, int]:
    """Get a dictionary of users on Discord with the specified reminder_time preference.

    Args:
        reminder_time: Get users that have set this as their preferred reminder time.

    Returns:
        Dictionary mapping tags to Discord IDs of Discord users that have reminder_time as their preference.
    """
    database, cursor = get_database_connection()

    if reminder_time == ReminderTime.ALL:
        cursor.execute("SELECT tag, discord_id FROM users")
    else:
        cursor.execute("SELECT tag, discord_id FROM users WHERE reminder_time = %s", reminder_time.value)

    database.close()
    return {user["tag"]: user["discord_id"] for user in cursor}


def get_clan_name(tag: str) -> Union[str, None]:
    """Get the name of a clan in the database from its tag.

    Args:
        tag: Tag of clan to get name of.

    Returns:
        Name of clan, or None if clan not in database.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT name FROM clans WHERE tag = %s", tag)
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return None

    return query_result["name"]


def get_player_report_data(tag: str) -> DatabaseReport:
    """Get data relevant to a player report from the database.

    Args:
        tag: Tag of user to get data of.

    Returns:
        Relevant data of user from database.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_name, strikes FROM users WHERE tag = %s", (tag))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return {
            "discord_name": "",
            "strikes": 0,
            "kicks": {}
        }

    kicks = get_kicks(tag)

    return {
        "discord_name": query_result["discord_name"],
        "strikes": query_result["strikes"],
        "kicks": kicks
    }


def get_discord_id_from_player_tag(tag: str) -> Optional[int]:
    """Get Discord ID of player associated with specified player tag.
   
    Args:
        tag: Tag of user to get Discord ID of.
   
    Returns:
        Discord ID of user, or None if they are not registered on Discord.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_id FROM users WHERE tag = %s", (tag))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return None

    return query_result["discord_id"]


############################################################################
#  __     __         _       _     _             _____     _     _         #
#  \ \   / /_ _ _ __(_) __ _| |__ | | ___  ___  |_   _|_ _| |__ | | ___    #
#   \ \ / / _` | '__| |/ _` | '_ \| |/ _ \/ __|   | |/ _` | '_ \| |/ _ \   #
#    \ V / (_| | |  | | (_| | |_) | |  __/\__ \   | | (_| | |_) | |  __/   #
#     \_/ \__,_|_|  |_|\__,_|_.__/|_|\___||___/   |_|\__,_|_.__/|_|\___|   #
#                                                                          #
############################################################################

def is_initialized() -> bool:
    """Check if database is fully initialized.

    Returns:
        Whether database is initialized.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT initialized FROM variables")
    database.close()
    return cursor.fetchone()["initialized"]


def get_guild_id() -> int:
    """Get saved Discord guild id.

    Returns:
        ID of saved Discord guild.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT guild_id FROM variables")
    query_result = cursor.fetchone()
    database.close()
    return query_result["guild_id"]


#######################################################################################
#    ____  _                       _   ___ ____     ____      _   _                   #
#   |  _ \(_)___  ___ ___  _ __ __| | |_ _|  _ \   / ___| ___| |_| |_ ___ _ __ ___    #
#   | | | | / __|/ __/ _ \| '__/ _` |  | || | | | | |  _ / _ \ __| __/ _ \ '__/ __|   #
#   | |_| | \__ \ (_| (_) | | | (_| |  | || |_| | | |_| |  __/ |_| ||  __/ |  \__ \   #
#   |____/|_|___/\___\___/|_|  \__,_| |___|____/   \____|\___|\__|\__\___|_|  |___/   #
#                                                                                     #
#######################################################################################

def get_clan_role_id(clan_role: ClanRole) -> Union[int, None]:
    """Get the Discord role ID associated with the specified clan role.

    Args:
        clan_role: Clan role to get associated Discord role ID of.

    Returns:
        ID of associated Discord role, or None if no Discord role is assigned.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_role_id FROM clan_role_discord_roles WHERE role = %s", (clan_role.value))
    query_result = cursor.fetchone()
    database.close()
    role_id = query_result["discord_role_id"] if query_result is not None else None
    return role_id


def get_special_role_id(special_role: SpecialRole) -> Union[int, None]:
    """Get the Discord role ID associated with the specified special role.

    Args:
        special_role: Special role to get associated Discord role ID of.

    Returns:
        ID of associated Discord role, or None if no Discord role is assigned.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_role_id FROM special_discord_roles WHERE role = %s", (special_role.value))
    query_result = cursor.fetchone()
    database.close()
    role_id = query_result["discord_role_id"] if query_result is not None else None
    return role_id


def get_special_channel_id(special_channel: SpecialChannel) -> Union[int, None]:
    """Get the Discord channel ID associated with the specified special channel.

    Args:
        special_channel: Special channel to get associated Discord channel ID of.

    Returns:
        ID of associated Discord channel, or None if no Discord channel is assigned.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_channel_id FROM special_discord_channels WHERE channel = %s", (special_channel.value))
    query_result = cursor.fetchone()
    database.close()
    channel_id = query_result["discord_channel_id"] if query_result is not None else None
    return channel_id


def get_clan_affiliated_channel_id(tag: str) -> Union[int, None]:
    """Get the Discord channel ID of the channel associated with the specified primary clan.

    Args:
        tag: Tag of primary clan to get channel for.

    Returns:
        ID of associated channel, or None if specified clan is not a primary clan.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_channel_id FROM primary_clans INNER JOIN clans ON primary_clans.clan_id = clans.id\
                    WHERE tag = %s",
                   (tag))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return None

    return query_result["discord_channel_id"]


def get_clan_affiliated_role_id(tag: str) -> Union[int, None]:
    """Get the Discord role ID of the role for members of the specified clan.

    Args:
        tag: Tag of clan to get role for.

    Returns:
        ID of role for specified clan. If clan is not in database, return Visitor role ID. If no Visitor role is set, then None.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_role_id FROM clans WHERE tag = %s", (tag))
    query_result = cursor.fetchone()

    if query_result is None:
        cursor.execute("SELECT discord_role_id FROM special_discord_roles WHERE role = %s", (SpecialRole.Visitor.value))
        query_result = cursor.fetchone()

        if query_result is None:
            query_result = {"discord_role_id": None}

    database.close()
    return query_result["discord_role_id"]


#####################################################################
#    ____  _        _     _____               _    _                #
#   / ___|| |_ __ _| |_  |_   _| __ __ _  ___| | _(_)_ __   __ _    #
#   \___ \| __/ _` | __|   | || '__/ _` |/ __| |/ / | '_ \ / _` |   #
#    ___) | || (_| | |_    | || | | (_| | (__|   <| | | | | (_| |   #
#   |____/ \__\__,_|\__|   |_||_|  \__,_|\___|_|\_\_|_| |_|\__, |   #
#                                                          |___/    #
#####################################################################

def tracks_stats(tag: str) -> bool:
    """Check if the specified clan tracks stats.

    Args:
        tag: Tag of clan to check.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT track_stats FROM primary_clans INNER JOIN clans ON primary_clans.clan_id = clans.id\
                    WHERE clans.tag = %s",
                   (tag))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return False

    return query_result["track_stats"]


def get_last_check(tag: str) -> datetime.datetime:
    """Get last time that Battle Day stats were checked for the specified clan.

    Returns:
        Time of last check.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT last_check FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    return query_result["last_check"]


def set_last_check(tag: str) -> datetime.datetime:
    """Set the last check time to current timestamp for the specified clan.

    Args:
        tag: Tag of clan to set last_check.

    Returns:
        New last_check value.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_races SET last_check = CURRENT_TIMESTAMP WHERE id = %s", (river_race_id))
    cursor.execute("SELECT last_check FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.commit()
    database.close()
    return query_result["last_check"]


def set_battle_time(tag: str):
    """Update a clan's river_race entry to indicate that its first Battle Day has begun.

    Args:
        tag: Tag of clan to update.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_races SET battle_time = TRUE WHERE id = %s", (river_race_id))
    database.commit()
    database.close()


def is_battle_time(tag: str) -> bool:
    """Check it it's currently a Battle Day.

    Args:
        tag: Tag of clan to check.

    Returns:
        Whether it's currently a Battle Day.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT battle_time FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return False

    return query_result["battle_time"]


def is_colosseum_week(tag: str) -> bool:
    """Check if it's currently a Colosseum week.

    Args:
        tag: Tag of clan to check.

    Returns:
        Whether it's currently Colosseum week.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT colosseum_week FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    return query_result["colosseum_week"]


def set_completed_saturday(tag: str, status: bool):
    """Set whether a clan crossed the finish line early.

    Args:
        tag: Tag of clan to set completion status of.
        status: Whether they crossed early or not.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_races SET completed_saturday = %s WHERE id = %s", (status, river_race_id))
    database.commit()
    database.close()


def is_completed_saturday(tag: str) -> bool:
    """Get whether a clan crossed the finish line early.

    Args:
        tag: Tag of clan to check race completion status of.

    Returns:
        Whether the specified clan crossed the finish line early.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT completed_saturday FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    return query_result["completed_saturday"]


def prepare_for_battle_days(tag: str):
    """Make necessary preparations to start tracking for upcoming Battle Days.

    Args:
        tag: Tag of clan to prepare for.
    """
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(tag)
    current_time = set_last_check(tag)
    set_battle_time(tag)

    try:
        add_unregistered_users(tag)
    except GeneralAPIError:
        LOG.warning(f"Unable to add unregistered users while preparing for battle days")

    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_race_user_data SET last_check = %s WHERE river_race_id = %s", (current_time, river_race_id))
    cursor.execute("UPDATE river_race_user_data SET tracked_since = %s WHERE river_race_id = %s AND\
                    clan_affiliation_id IN (SELECT id FROM clan_affiliations WHERE clan_id = %s AND role IS NOT NULL)",
                   (current_time, river_race_id, clan_id))

    try:
        update_cards_in_database(cursor)
    except GeneralAPIError:
        LOG.warning("Unable to check for potential card updates")

    database.commit()
    database.close()

    try:
        update_river_race_clans(tag)
    except GeneralAPIError:
        LOG.warning(f"Unable to get clans during battle day preparations for clan {tag}")


def update_river_race_clans(tag: str):
    """Insert/update clans used for predictions for a primary clan. If they already exist for the current season, don't do anything.

    Args:
        tag: Tag of clan to insert River Race clans for.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    _, clan_id, season_id, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    clans_in_race = clash_utils.get_clans_in_race(tag, False)
    cursor.execute("SELECT id FROM river_race_clans WHERE clan_id = %s AND season_id = %s", (clan_id, season_id))
    insert_new_clans = not bool(cursor.fetchall())

    for clan_tag, clan in clans_in_race.items():
        if insert_new_clans:
            LOG.info(log_message("Inserting River Race clan",
                                 clan_id=clan_id,
                                 season_id=season_id,
                                 clan_tag=clan_tag))
            cursor.execute("INSERT INTO river_race_clans (clan_id, season_id, tag, name, current_race_total_decks) VALUES\
                            (%s, %s, %s, %s, %s)",
                           (clan_id, season_id, clan_tag, clan["name"], clan["total_decks_used"]))
        else:
            LOG.info(log_message("Updating River Race clan",
                                 clan_id=clan_id,
                                 season_id=season_id,
                                 clan_tag=clan_tag))
            cursor.execute("UPDATE river_race_clans SET current_race_medals = 0, current_race_total_decks = %s\
                            WHERE clan_id = %s AND season_id = %s AND tag = %s",
                           (clan["total_decks_used"], clan_id, season_id, clan_tag))

    database.commit()
    database.close()


def set_clan_reset_time(tag: str, weekday: int):
    """Set a clan's daily reset time. Used for times when API is down and reset time cannot be detected.

    Args:
        tag: Tag of clan to set reset time for.
        weekday: Which day to set reset time for.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)

    if river_race_id is None:
        LOG.warning(log_message("Missing river_races entry", tag=tag, weekday=weekday))
        return

    if weekday:
        day_key = f"day_{weekday}"
    else:
        day_key = "day_7"

    database, cursor = get_database_connection()
    reset_time_query = f"UPDATE river_races SET {day_key} = CURRENT_TIMESTAMP WHERE id = %s"
    cursor.execute(reset_time_query, (river_race_id))
    database.commit()
    database.close()


def record_deck_usage_today(tag: str, weekday: int, deck_usage: Dict[str, Tuple[int, int]]):
    """Log daily deck usage for each member of a clan and record reset time.

    Args:
        tag: Tag of clan to log deck usage for.
        weekday: Which day usage is being logged on.
        reset_time: Time that daily reset occurred.
        deck_usage: Dictionary of player tags mapped to their decks used today and total decks used in the specified clan.
    """
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(tag)

    if river_race_id is None:
        LOG.warning(log_message("Missing river_races entry", tag=tag, weekday=weekday))
        return

    if weekday:
        day_key = f"day_{weekday}"
    else:
        day_key = "day_7"

    active_key = day_key + "_active"
    locked_key = day_key + "_locked"
    active_members = clash_utils.get_active_members_in_clan(tag)

    database, cursor = get_database_connection()
    reset_time_query = f"UPDATE river_races SET {day_key} = CURRENT_TIMESTAMP WHERE id = %s"
    cursor.execute(reset_time_query, (river_race_id))

    last_check = get_last_check(tag)

    if day_key in {"day_4", "day_5", "day_6", "day_7"}:
        update_usage_query = ("INSERT INTO river_race_user_data "
                              f"(clan_affiliation_id, river_race_id, last_check, {day_key}, {active_key}, {locked_key}) VALUES "
                              "(%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s, %(decks_used)s, %(is_active)s, %(locked_out)s) "
                              f"ON DUPLICATE KEY UPDATE {day_key} = %(decks_used)s, {active_key} = %(is_active)s, {locked_key} = %(locked_out)s, last_check = last_check")
    else:
        update_usage_query = ("INSERT INTO river_race_user_data "
                              f"(clan_affiliation_id, river_race_id, last_check, {day_key}, {active_key}) VALUES "
                              "(%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s, %(decks_used)s, %(is_active)s) "
                              f"ON DUPLICATE KEY UPDATE {day_key} = %(decks_used)s, {active_key} = %(is_active)s, last_check = last_check")

    update_query_dict = {
        "clan_affiliation_id": None,
        "river_race_id": river_race_id,
        "last_check": last_check,
        "decks_used": None,
        "is_active": None,
        "locked_out": None
    }

    max_participation = len([decks_used for (decks_used, _) in deck_usage.values() if decks_used > 0]) == 50

    for player_tag, (decks_used, _) in deck_usage.items():
        cursor.execute("SELECT id FROM users WHERE tag = %s", (player_tag))
        query_result = cursor.fetchone()

        if query_result is None:
            LOG.debug(log_message("Inserting new user for deck usage tracking", player_tag=player_tag, clan_tag=tag))
            try:
                clash_data = clash_utils.get_clash_royale_user_data(player_tag)
            except GeneralAPIError:
                LOG.warning(log_message("Failed to add new user while recording deck usage"))
                continue

            insert_new_user(clash_data, cursor=cursor)
            cursor.execute("SELECT id FROM users WHERE tag = %s", (player_tag))
            query_result = cursor.fetchone()

        user_id = query_result["id"]
        cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %s AND clan_id = %s", (user_id, clan_id))
        query_result = cursor.fetchone()

        if query_result is None:
            LOG.debug(log_message("Creating new clan affiliation", player_tag=player_tag, clan_tag=tag))
            cursor.execute("INSERT INTO clan_affiliations (user_id, clan_id) VALUES (%s, %s)", (user_id, clan_id))
            cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %s AND clan_id = %s", (user_id, clan_id))
            query_result = cursor.fetchone()

        update_query_dict["is_active"] = player_tag in active_members

        if update_query_dict["is_active"] and max_participation and decks_used == 0:
            update_query_dict["locked_out"] = True

        update_query_dict["clan_affiliation_id"] = query_result["id"]
        update_query_dict["decks_used"] = decks_used

        cursor.execute(update_usage_query, update_query_dict)

    database.commit()
    database.close()


def get_medal_counts(tag: str) -> Dict[str, Tuple[int, datetime.datetime]]:
    """Get the current medal count and last check time of each user in a clan.

    Args:
        tag: Tag of clan to get data from.

    Returns:
        Dictionary mapping player tags to their medals and last check times for the current River Race of the specified clan.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag)

    if river_race_id is None:
        LOG.warning(f"Could not find River Race entry for clan {tag}")
        return []

    database, cursor = get_database_connection()
    cursor.execute("SELECT users.tag AS tag, river_race_user_data.medals AS medals, river_race_user_data.last_check AS last_check\
                    FROM users\
                    INNER JOIN clan_affiliations ON clan_affiliations.user_id = users.id\
                    INNER JOIN river_race_user_data ON river_race_user_data.clan_affiliation_id = clan_affiliations.id\
                    WHERE river_race_user_data.river_race_id = %s",
                   (river_race_id))
    database.close()
    results = {user["tag"]: (user["medals"], user["last_check"]) for user in cursor}
    return results


def record_battle_day_stats(stats: List[Tuple[BattleStats, Battles, int]], last_check: datetime.datetime, api_is_broken: bool):
    """Update users' Battle Day stats with their latest matches.

    Args:
        stats: List of tuples of users' stats and medal counts.
        last_check: Value to update users' last_check times to.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.
    """
    if not stats:
        return

    clan_tag = stats[0][0]["clan_tag"]
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(clan_tag)

    if river_race_id is None:
        LOG.warning(log_message("Missing river_races entry", clan_tag=clan_tag))
        return

    database, cursor = get_database_connection()

    for user_stats, battles, medals in stats:
        user_stats["medals"] = medals
        user_stats["river_race_id"] = river_race_id
        user_stats["clan_id"] = clan_id
        user_stats["last_check"] = last_check
        cursor.execute("SELECT id FROM users WHERE tag = %(player_tag)s", user_stats)
        query_result = cursor.fetchone()

        if query_result is None:
            try:
                clash_data = clash_utils.get_clash_royale_user_data(user_stats["player_tag"])
            except GeneralAPIError:
                LOG.warning(log_message("Failed to insert new user", clash_data=clash_data))
                continue

            insert_new_user(clash_data, cursor=cursor)
            cursor.execute("SELECT id FROM users WHERE tag = %(player_tag)s", user_stats)
            query_result = cursor.fetchone()

        user_stats["user_id"] = query_result["id"]
        cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", user_stats)
        query_result = cursor.fetchone()

        if query_result is None:
            cursor.execute("INSERT INTO clan_affiliations (user_id, clan_id) VALUES (%(user_id)s, %(clan_id)s)", user_stats)
            cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", user_stats)
            query_result = cursor.fetchone()

        user_stats["clan_affiliation_id"] = query_result["id"]
        cursor.execute("INSERT INTO river_race_user_data (\
                            clan_affiliation_id,\
                            river_race_id,\
                            last_check,\
                            tracked_since,\
                            medals,\
                            regular_wins,\
                            regular_losses,\
                            special_wins,\
                            special_losses,\
                            duel_wins,\
                            duel_losses,\
                            series_wins,\
                            series_losses,\
                            boat_wins,\
                            boat_losses\
                        ) VALUES (\
                            %(clan_affiliation_id)s,\
                            %(river_race_id)s,\
                            %(last_check)s,\
                            CURRENT_TIMESTAMP,\
                            %(medals)s,\
                            %(regular_wins)s,\
                            %(regular_losses)s,\
                            %(special_wins)s,\
                            %(special_losses)s,\
                            %(duel_wins)s,\
                            %(duel_losses)s,\
                            %(series_wins)s,\
                            %(series_losses)s,\
                            %(boat_wins)s,\
                            %(boat_losses)s\
                        ) ON DUPLICATE KEY UPDATE\
                            last_check = %(last_check)s,\
                            tracked_since = COALESCE(tracked_since, CURRENT_TIMESTAMP),\
                            medals = %(medals)s,\
                            regular_wins = regular_wins + %(regular_wins)s,\
                            regular_losses = regular_losses + %(regular_losses)s,\
                            special_wins = special_wins + %(special_wins)s,\
                            special_losses = special_losses + %(special_losses)s,\
                            duel_wins = duel_wins + %(duel_wins)s,\
                            duel_losses = duel_losses + %(duel_losses)s,\
                            series_wins = series_wins + %(series_wins)s,\
                            series_losses = series_losses + %(series_losses)s,\
                            boat_wins = boat_wins + %(boat_wins)s,\
                            boat_losses = boat_losses + %(boat_losses)s",
                       user_stats)

        for battle in battles["pvp_battles"]:
            insert_pvp_battle(battle, user_stats["clan_affiliation_id"], user_stats["river_race_id"], cursor, api_is_broken)

        for duel in battles["duels"]:
            insert_duel(duel, user_stats["clan_affiliation_id"], user_stats["river_race_id"], cursor, api_is_broken)

        for boat_battle in battles["boat_battles"]:
            insert_boat_battle(boat_battle, user_stats["clan_affiliation_id"], user_stats["river_race_id"], cursor, api_is_broken)

    database.commit()
    database.close()


def update_cards_in_database(cursor: Optional[pymysql.cursors.DictCursor]=None) -> bool:
    """Add any new cards that may have been added to the database and update any existing ones that have had their names, url, or
       max level changed.

    Args:
        cursor: Cursor used to interact with database. If not provided, will create a new one. Otherwise, use the one provided.
                Caller is responsible for committing changes made by cursor if provided.

    Returns:
        TEMPORARY: Until Supercell fixes their API to account for level 15 cards, this function returns true if the highest detected
                   level is still 14.

    Raises:
        GeneralAPIError: Something went wrong getting list of current cards from Clash Royale API.
    """
    close_connection = False
    current_cards = clash_utils.get_all_cards()

    max_card_level = 0

    for card in current_cards:
        if card["max_level"] > max_card_level:
            max_card_level = card["max_level"]

    api_is_broken = max_card_level < 15

    if cursor is None:
        close_connection = True
        database, cursor = get_database_connection()

    cursor.execute("SELECT * FROM cards")
    query_result = cursor.fetchall()
    db_cards_dict = {card["id"] : card for card in query_result}

    if not os.path.exists(CARD_IMAGE_PATH):
        os.makedirs(CARD_IMAGE_PATH)

    for card in current_cards:
        id = card["id"]

        if id not in db_cards_dict:
            LOG.info(log_message("Adding new card to database", id=id, name=card["name"]))
            cursor.execute("INSERT INTO cards VALUES (%(id)s, %(name)s, %(max_level)s, %(url)s)", card)
            file_name = str(card["id"]) + ".png"
            card_path = os.path.join(CARD_IMAGE_PATH, file_name)

            with open(card_path, 'wb') as card_file:
                card_file.write(requests.get(card["url"]).content)

        elif ((card["name"] != db_cards_dict[id]["name"])
                or (card["max_level"] != db_cards_dict[id]["max_level"])
                or (card["url"] != db_cards_dict[id]["url"])):
            LOG.info(log_message("Updating existing card in database",
                                 id=id,
                                 orig_name=db_cards_dict[id]["name"],
                                 new_name=card["name"],
                                 orig_max_level=db_cards_dict[id]["max_level"],
                                 new_max_level=card["max_level"],
                                 orig_url=db_cards_dict[id]["url"],
                                 new_url=card["url"]))
            cursor.execute("UPDATE cards SET name = %(name)s, max_level = %(max_level)s, url = %(url)s WHERE id = %(id)s",
                           card)

            if card["url"] != db_cards_dict[id]["url"]:
                file_name = str(card["id"]) + ".png"
                card_path = os.path.join(CARD_IMAGE_PATH, file_name)
                os.remove(card_path)

                with open(card_path, 'wb') as card_file:
                    card_file.write(requests.get(card["url"]).content)

    if close_connection:
        database.commit()
        database.close()

    return api_is_broken


def insert_deck(deck: List[Card], cursor: pymysql.cursors.DictCursor, api_is_broken: bool) -> int:
    """Insert a deck into the decks table if it doesn't exist.

    Args:
        deck: List of Cards to insert.
        cursor: Cursor to use to insert deck.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.

    Returns:
        id of deck.
    """
    deck.sort(key=lambda x: x["id"])
    card_id_str = ",".join(str(card["id"]) for card in deck)

    if api_is_broken:
        card_level_str = ",".join(str(card["level"] - (card["max_level"] + 1)) for card in deck)
    else:
        card_level_str = ",".join(str(card["level"] - card["max_level"]) for card in deck)

    cursor.execute("SELECT deck_id,\
                           GROUP_CONCAT(card_id ORDER BY card_id) AS cards,\
                           GROUP_CONCAT(card_level ORDER BY card_id) AS card_levels\
                    FROM deck_cards\
                    GROUP BY deck_id\
                    HAVING cards = %s AND card_levels = %s",
                   (card_id_str, card_level_str))

    query_result = cursor.fetchone()

    if query_result is None:
        cursor.execute("INSERT INTO decks VALUES (DEFAULT)")
        cursor.execute("SELECT LAST_INSERT_ID() as deck_id")
        deck_id = cursor.fetchone()["deck_id"]

        for card in deck:
            card["deck_id"] = deck_id

            if api_is_broken:
                card["level_offset"] = card["level"] - (card["max_level"] + 1)
            else:
                card["level_offset"] = card["level"] - card["max_level"]

        cursor.executemany("INSERT INTO deck_cards VALUES (%(deck_id)s, %(id)s, %(level_offset)s)", deck)
    else:
        deck_id = query_result["deck_id"]

    return deck_id


def insert_pvp_battle(battle: PvPBattle, clan_affiliation_id: int, river_race_id: int, cursor: pymysql.cursors.DictCursor, api_is_broken: bool) -> int:
    """Insert an individual PvP battle into the pvp_battles table.

    Args:
        battle: Info about the battle.
        clan_affiliation_id: Clan affiliation id of primary clan member who participated in the battle.
        river_race_id: Id of river race in which battle took place.
        cursor: Cursor to use to insert the battle.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.

    Returns:
        id of newly inserted PvP battle.
    """
    battle_dict = {
        "clan_affiliation_id": clan_affiliation_id,
        "river_race_id": river_race_id,
        "time": battle["time"],
        "game_type": battle["game_type"],
        "won": battle["won"],
        "deck_id": insert_deck(battle["team_results"]["deck"], cursor, api_is_broken),
        "crowns": battle["team_results"]["crowns"],
        "elixir_leaked": battle["team_results"]["elixir_leaked"],
        "kt_hit_points": battle["team_results"]["kt_hit_points"],
        "pt1_hit_points": battle["team_results"]["pt1_hit_points"],
        "pt2_hit_points": battle["team_results"]["pt2_hit_points"],
        "opp_deck_id": insert_deck(battle["opponent_results"]["deck"], cursor, api_is_broken),
        "opp_crowns": battle["opponent_results"]["crowns"],
        "opp_elixir_leaked": battle["opponent_results"]["elixir_leaked"],
        "opp_kt_hit_points": battle["opponent_results"]["kt_hit_points"],
        "opp_pt1_hit_points": battle["opponent_results"]["pt1_hit_points"],
        "opp_pt2_hit_points": battle["opponent_results"]["pt2_hit_points"]
    }

    cursor.execute("INSERT INTO pvp_battles VALUES (\
                    DEFAULT, %(clan_affiliation_id)s, %(river_race_id)s, %(time)s, %(game_type)s,\
                    %(won)s, %(deck_id)s, %(crowns)s, %(elixir_leaked)s, %(kt_hit_points)s,\
                    %(pt1_hit_points)s, %(pt2_hit_points)s, %(opp_deck_id)s, %(opp_crowns)s,\
                    %(opp_elixir_leaked)s, %(opp_kt_hit_points)s, %(opp_pt1_hit_points)s,\
                    %(opp_pt2_hit_points)s)",
                   battle_dict)

    cursor.execute("SELECT LAST_INSERT_ID() as id")
    query_result = cursor.fetchone()
    return query_result["id"]


def insert_duel(duel: Duel, clan_affiliation_id: int, river_race_id: int, cursor: pymysql.cursors.DictCursor, api_is_broken: bool):
    """Insert a duel into the duels table.

    Args:
        duel: Info about the duel.
        clan_affiliation_id: Clan affiliation id of primary clan member who participated in the duel.
        river_race_id: Id of river race in which duel took place.
        cursor: Cursor to use to insert the duel.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.
    """
    duel_dict = {
        "clan_affiliation_id": clan_affiliation_id,
        "river_race_id": river_race_id,
        "time": duel["time"],
        "won": duel["won"],
        "battle_wins": duel["battle_wins"],
        "battle_losses": duel["battle_losses"],
        "round_1": None,
        "round_2": None,
        "round_3": None
    }

    for i, battle in enumerate(duel["battles"], 1):
        duel_dict[f"round_{i}"] = insert_pvp_battle(battle, clan_affiliation_id, river_race_id, cursor, api_is_broken)

    cursor.execute("INSERT INTO duels VALUES (\
                    DEFAULT, %(clan_affiliation_id)s, %(river_race_id)s, %(time)s, %(won)s,\
                    %(battle_wins)s, %(battle_losses)s, %(round_1)s, %(round_2)s, %(round_3)s)",
                   duel_dict)


def insert_boat_battle(boat_battle: BoatBattle, clan_affiliation_id: int, river_race_id: int, cursor: pymysql.cursors.DictCursor, api_is_broken: bool):
    """Insert a boat battle into the boat_battles table.

    Args:
        boat_battle: Info about the boat battle.
        clan_affiliation_id: Clan affiliation id of primary clan member who participated in the boat battle.
        river_race_id: Id of river race in which boat battle took place.
        cursor: Cursor to use to insert the boat battle.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.
    """
    boat_dict = {
        "clan_affiliation_id": clan_affiliation_id,
        "river_race_id": river_race_id,
        "time": boat_battle["time"],
        "deck_id": insert_deck(boat_battle["deck"], cursor, api_is_broken),
        "elixir_leaked": boat_battle["elixir_leaked"],
        "new_towers_destroyed": boat_battle["new_towers_destroyed"],
        "prev_towers_destroyed": boat_battle["prev_towers_destroyed"],
        "remaining_towers": boat_battle["remaining_towers"]
    }

    cursor.execute("INSERT INTO boat_battles VALUES (DEFAULT,\
                    %(clan_affiliation_id)s, %(river_race_id)s, %(time)s, %(deck_id)s, %(elixir_leaked)s,\
                    %(new_towers_destroyed)s, %(prev_towers_destroyed)s, %(remaining_towers)s)",
                   boat_dict)


def get_current_season_river_race_clans(tag: str) -> Dict[str, DatabaseRiverRaceClan]:
    """Get the saved data for all clans in the specified clan's current season River Races.

    Args:
        tag: Tag of clan to get saved data from.

    Returns:
        Dictionary mapping clan tags to their saved data.
    """
    _, clan_id, season_id, _ = get_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT * FROM river_race_clans WHERE clan_id = %s AND season_id = %s", (clan_id, season_id))
    database.close()
    return {clan["tag"]: clan for clan in cursor}


def update_current_season_river_race_clans(updated_data: List[DatabaseRiverRaceClan]):
    """Update saved data of River Race clans with latest data.

    Args:
        updated_data: List of latest clan data to save.
    """
    database, cursor = get_database_connection()
    cursor.executemany("UPDATE river_race_clans SET\
                        current_race_medals = %(current_race_medals)s,\
                        total_season_medals = %(total_season_medals)s,\
                        current_race_total_decks = %(current_race_total_decks)s,\
                        total_season_battle_decks = %(total_season_battle_decks)s,\
                        battle_days = %(battle_days)s\
                        WHERE id = %(id)s",
                       updated_data)
    database.commit()
    database.close()


def create_new_season():
    """Create a new season index."""
    LOG.info("Creating new season")
    database, cursor = get_database_connection()
    cursor.execute("INSERT INTO seasons VALUES (DEFAULT, DEFAULT)")
    database.commit()
    database.close()


def prepare_for_river_race(tag: str):
    """Insert a new river_race entry for the specified clan.

    Args:
        tag: Tag of clan to create entries for.
    """
    LOG.info(f"Creating new river race entry for {tag}")
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    clan_id = cursor.fetchone()["id"]
    cursor.execute("SELECT MAX(id) AS id FROM seasons")
    season_id = cursor.fetchone()["id"]

    week = 1
    delta = datetime.timedelta(days=7)
    date = datetime.datetime.utcnow()
    current_month = date.month
    date -= delta

    while date.month == current_month:
        date -= delta
        week += 1

    river_race_info = {
        "clan_id": clan_id,
        "season_id": season_id,
        "week": week,
        "colosseum_week": clash_utils.is_colosseum_week(),
        "completed_saturday": False
    }

    cursor.execute("INSERT INTO river_races (clan_id, season_id, week, start_time, colosseum_week, completed_saturday)\
                    VALUES (%(clan_id)s, %(season_id)s, %(week)s, CURRENT_TIMESTAMP, %(colosseum_week)s, %(completed_saturday)s)",
                   river_race_info)

    database.commit()
    database.close()


def get_stats(player_tag: str, clan_tag: Optional[str]=None) -> BattleStats:
    """Get a user's all time Battle Day stats.

    Args:
        player_tag: Tag of user to get stats of.
        clan_tag: Get stats of user while in this clan. If None, then get combined stats.

    Returns:
        All time stats dictionary.
    """
    database, cursor = get_database_connection()
    stats: BattleStats = {
        "player_tag": player_tag,
        "clan_tag": clan_tag,
        "regular_wins": 0,
        "regular_losses": 0,
        "special_wins": 0,
        "special_losses": 0,
        "duel_wins": 0,
        "duel_losses": 0,
        "series_wins": 0,
        "series_losses": 0,
        "boat_wins": 0,
        "boat_losses": 0
    }
    cursor.execute("SELECT id FROM users WHERE tag = %s", (player_tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return stats

    user_id = query_result["id"]

    if clan_tag is None:
        cursor.execute("SELECT * FROM river_race_user_data\
                        WHERE clan_affiliation_id IN (SELECT id FROM clan_affiliations WHERE user_id = %s)",
                       (user_id))
    else:
        cursor.execute("SELECT id FROM clans WHERE tag = %s", (clan_tag))
        query_result = cursor.fetchone()

        if query_result is None:
            database.close()
            return stats

        clan_id = query_result["id"]
        cursor.execute("SELECT * FROM river_race_user_data\
                        WHERE clan_affiliation_id = (SELECT id FROM clan_affiliations WHERE user_id = %s AND clan_id = %s)",
                       (user_id, clan_id))

    database.close()

    for race_data in cursor:
        stats["regular_wins"] += race_data["regular_wins"]
        stats["regular_losses"] += race_data["regular_losses"]
        stats["special_wins"] += race_data["special_wins"]
        stats["special_losses"] += race_data["special_losses"]
        stats["duel_wins"] += race_data["duel_wins"]
        stats["duel_losses"] += race_data["duel_losses"]
        stats["series_wins"] += race_data["series_wins"]
        stats["series_losses"] += race_data["series_losses"]
        stats["boat_wins"] += race_data["boat_wins"]
        stats["boat_losses"] += race_data["boat_losses"]

    return stats


def time_in_clan(player_tag: str, clans: List[str]) -> datetime.timedelta:
    """Get the amount of time a user has spent in the specified clans.

    Args:
        player_tag: Tag of user to check.
        clans: List of clan tags. Will sum up time spent in each of these clans.

    Returns:
        Time spent in specified clans.
    """
    tags = clans.copy()

    for i, tag in enumerate(tags):
        tags[i] = "'" + tag + "'"

    clan_tags_str = ", ".join(tags)
    query = ("SELECT * FROM clan_time WHERE clan_affiliation_id IN ("
             "SELECT id FROM clan_affiliations WHERE "
             "user_id = (SELECT id FROM users WHERE tag = %s) AND "
             f"clan_id IN (SELECT id FROM clans WHERE tag IN ({clan_tags_str})))")

    database, cursor = get_database_connection()
    cursor.execute(query, (player_tag))
    time_in_clans = datetime.timedelta()
    now = datetime.datetime.utcnow()

    for time_period in cursor:
        if time_period["end"] is None:
            time_in_clans += now - time_period["start"]
        else:
            time_in_clans += time_period["end"] - time_period["start"]

    database.close()
    return time_in_clans


def get_clan_times(clan_affiliation_id: int) -> List[Tuple[datetime.datetime, Union[datetime.datetime, None]]]:
    """Get a list of time periods that a user was in a clan.

    Args:
        clan_affiliation_id: ID of clan affiliation to check.

    Return:
        List of time ranges that user was in the clan. If they are currently in the clan, the end time of one entry will be None.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT * FROM clan_time WHERE clan_affiliation_id = %s", (clan_affiliation_id))
    clan_times = [(time_range["start"], time_range["end"]) for time_range in cursor.fetchall()]
    clan_times.sort(key=lambda time_range: time_range[0])
    database.close()
    return clan_times


def get_name_and_tag_from_affiliation(clan_affiliation_id: int) -> Union[Tuple[str, str], Tuple[None, None]]:
    """Get a user's player name and tag from their clan affiliation id.

    Args:
        clan_affiliation_id: Clan affiliation ID to get user data from.

    Returns:
        Tuple of the user's name and tag.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT name, tag FROM users WHERE id = (SELECT user_id FROM clan_affiliations WHERE id = %s)",
                   (clan_affiliation_id))
    database.close()
    query_result = cursor.fetchone()

    if query_result is None:
        return (None, None)

    return (query_result["name"], query_result["tag"])


########################################
#    ____  _        _ _                #
#   / ___|| |_ _ __(_) | _____  ___    #
#   \___ \| __| '__| | |/ / _ \/ __|   #
#    ___) | |_| |  | |   <  __/\__ \   #
#   |____/ \__|_|  |_|_|\_\___||___/   #
#                                      #
########################################

def correct_reset_times(reset_times: List[Union[datetime.datetime, None]]) -> List[datetime.datetime]:
    """Given a clan's reset times, fill in any missing days.

    Args:
        reset_times: List of reset times in order to correct.

    Returns:
        List of times with missing entries filled in, or empty list if not possible.
    """
    times = reset_times.copy()

    if not all(times):
        if not any(times):
            return []

        for i in range(len(times)):
            if not times[i]:
                next_index = (i + 1) % len(times)

                while next_index != i:
                    if times[next_index]:
                        diff = i - next_index

                        if diff > 0:
                            times[i] = times[next_index] + datetime.timedelta(days=diff)
                        else:
                            times[i] = times[next_index] - datetime.timedelta(days=-diff)
                    else:
                        next_index = (next_index + 1) % len(times)

                if next_index == i:
                    return []

    return times

def get_clan_strike_determination_data(tag: str) -> Union[ClanStrikeInfo, None]:
    """Get data needed from a clan's most recent River Race to determine who should receive a strike.

    Args:
        tag: Tag of clan to get strike data for.
    """
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(tag, 1)

    if river_race_id is None:
        LOG.error("Could not find ID of most recent River Race")
        return None

    database, cursor = get_database_connection()
    strike_info: ClanStrikeInfo = {}
    strike_info["river_race_id"] = river_race_id

    cursor.execute("SELECT strike_threshold FROM primary_clans WHERE clan_id = %s", (clan_id))
    query_result = cursor.fetchone()
    strike_info["strike_threshold"] = query_result["strike_threshold"]

    cursor.execute("SELECT completed_saturday, day_3, day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    strike_info["completed_saturday"] = query_result["completed_saturday"]
    reset_times: List[datetime.datetime] = [query_result[day_key] for day_key in ["day_3", "day_4", "day_5", "day_6", "day_7"]]
    database.close()

    reset_times = correct_reset_times(reset_times)

    if not reset_times:
        LOG.warning("Unable to correct missing reset time(s)")
        return None

    strike_info["reset_times"] = reset_times
    return strike_info


def get_river_race_user_data(river_race_id: int) -> List[RiverRaceUserData]:
    """Get a list of all river_race_user_data entries for the specified River Race.

    Args:
        river_race_id: ID of race to get entries for.

    Returns:
        Unmodified river_race_user_data entries from database.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT * FROM river_race_user_data WHERE river_race_id = %s", (river_race_id))
    database.close()
    return [river_race_user_data_row for river_race_user_data_row in cursor.fetchall()]


def update_strikes(search_key: Union[int, str], delta: int) -> Tuple[Union[int, None], Union[int, None]]:
    """Give or remove strikes to a user.

    Args:
        search_key: Either the Discord ID or player tag of the user to update strikes for.
        delta: Number of strikes to give or take.

    Returns:
        Tuple of previous strike count and updated strike count, or (None, None) if user is not in database.
    """
    database, cursor = get_database_connection()

    if isinstance(search_key, int):
        cursor.execute("SELECT id, strikes FROM users WHERE discord_id = %s", (search_key))
    elif isinstance(search_key, str):
        cursor.execute("SELECT id, strikes FROM users WHERE tag = %s", (search_key))
    else:
        LOG.warning(log_message("Tried updating strikes with invalid search key", search_key=search_key, delta=delta))
        database.close()
        return (None, None)

    query_result = cursor.fetchone()

    if query_result is None:
        LOG.debug(log_message("Tried updating strikes of user not in database", search_key=search_key, delta=delta))
        database.close()
        return (None, None)

    user_id = query_result["id"]
    previous_strike_count = query_result["strikes"]
    updated_strike_count = previous_strike_count + delta

    if updated_strike_count < 0:
        updated_strike_count = 0

    cursor.execute("UPDATE users SET strikes = %s WHERE id = %s", (updated_strike_count, user_id))
    database.commit()
    database.close()
    return (previous_strike_count, updated_strike_count)


def get_strike_count(id: int) -> int:
    """Get how many strikes a user has.

    Args:
        id: Discord ID of user to check.

    Returns:
        Number of strikes that specified user has.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT strikes FROM users WHERE discord_id = %s", (id))
    query_result = cursor.fetchone()
    database.close()

    if query_result is None:
        return 0

    return query_result["strikes"]


def remedy_deck_usage(tag: str,
                      weekday: int,
                      pre_reset_usage: Dict[str, Tuple[int, int]],
                      post_reset_usage: Dict[str, Tuple[int, int]]):
    """Fix any situations where a user completed a River Race battle in between the two final reset time checks.

    Args:
        tag: Tag of clan to fix deck usage for.
        weekday: Which day to update.
        pre_reset_usage: Saved deck usage immediately before daily reset.
        post_reset_usage: Saved deck usage immediately after daily reset.
    """
    database, cursor = get_database_connection()
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(tag)

    if weekday:
        day_key = f"day_{weekday}"
    else:
        day_key = "day_7"

    for player_tag, (decks_used_today, decks_used) in pre_reset_usage.items():
        if (player_tag in post_reset_usage
                and decks_used_today < 4
                and post_reset_usage[player_tag][0] == 0
                and post_reset_usage[player_tag][1] > decks_used):
            actual_decks_used_today = decks_used_today + (post_reset_usage[player_tag][1] - decks_used)

            LOG.info(log_message("Remedying daily deck usage",
                                 player_tag=player_tag,
                                 clan_tag=tag,
                                 weekday=day_key,
                                 river_race_id=river_race_id,
                                 clan_id=clan_id,
                                 pre_decks_used_today=decks_used_today,
                                 pre_decks_used=decks_used,
                                 post_decks_used_today=post_reset_usage[player_tag][0],
                                 post_decks_used=post_reset_usage[player_tag][1],
                                 actual_decks_used_today=actual_decks_used_today))

            if actual_decks_used_today > 4:
                LOG.warning("Skipping daily deck usage update due to excessive decks used today.")
                continue

            cursor.execute("SELECT id FROM clan_affiliations WHERE clan_id = %s AND user_id = (SELECT id FROM users WHERE tag = %s)",
                           (clan_id, player_tag))
            query_result = cursor.fetchone()

            if query_result is None:
                LOG.warning("Skipping daily deck usage update due to not finding relevant clan affiliation.")
                continue

            clan_affiliation_id = query_result["id"]
            query = (f"UPDATE river_race_user_data SET {day_key} = %s, last_check = last_check "
                     "WHERE clan_affiliation_id = %s AND river_race_id = %s")
            cursor.execute(query, (actual_decks_used_today, clan_affiliation_id, river_race_id))

    database.commit()
    database.close()


def fix_anomalies(tag: str):
    """After a River Race finishes, attempt to fix any anomalies caused by API issues.

    Args:
        tag: Tag of clan to attempt to fix.
    """
    river_race_id, _, _, _ = get_clan_river_race_ids(tag, 1)
    river_race_user_data = get_river_race_user_data(river_race_id)
    database, cursor = get_database_connection()
    day_keys = ["day_4", "day_5", "day_6", "day_7"]

    cursor.execute("SELECT day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    reset_times: List[datetime.datetime] = [query_result[day_key] for day_key in day_keys]
    reset_times = correct_reset_times(reset_times)

    if not reset_times:
        LOG.warning("Unable to correct missing reset time(s)")
        return

    for user_data in river_race_user_data:
        for day_key in day_keys:
            if user_data[day_key] is None:
                user_data[day_key] = 0

        deck_usage_sum = user_data["day_4"] + user_data["day_5"] + user_data["day_6"] + user_data["day_7"]

        stats_sum = (user_data["regular_wins"] +
                     user_data["regular_losses"] +
                     user_data["special_wins"] +
                     user_data["special_losses"] +
                     user_data["duel_wins"] +
                     user_data["duel_losses"] +
                     user_data["boat_wins"] +
                     user_data["boat_losses"])

        if deck_usage_sum < stats_sum:
            clan_affiliation_id = user_data["clan_affiliation_id"]

            LOG.info(log_message("Mismatched daily deck usage and stats usage",
                                 clan_affiliation_id=clan_affiliation_id,
                                 river_race_id=river_race_id,
                                 deck_usage_sum=deck_usage_sum,
                                 stats_sum=stats_sum))

            actual_medals = user_data["medals"]
            calculated_medals = ((200 * (user_data["regular_wins"] + user_data["special_wins"])) +
                                 (100 * (user_data["regular_losses"] + user_data["special_losses"] + user_data["duel_losses"])) +
                                 (250 * user_data["duel_wins"]) +
                                 (125 * user_data["boat_wins"]) +
                                 (75 * user_data["boat_losses"]))

            if actual_medals != calculated_medals:
                LOG.warning(log_message("Incorrect medals data, cannot proceed",
                                        actual_medals=actual_medals,
                                        calculated_medals=calculated_medals))
                continue

            cursor.execute("SELECT time FROM boat_battles WHERE clan_affiliation_id = %s AND river_race_id = %s",
                           (clan_affiliation_id, river_race_id))
            boat_battles: List[datetime.datetime] = [battle["time"] for battle in cursor]

            cursor.execute("SELECT time FROM pvp_battles WHERE clan_affiliation_id = %s AND river_race_id = %s",
                           (clan_affiliation_id, river_race_id))
            pvp_battles: List[datetime.datetime] = [battle["time"] for battle in cursor]
            all_battles = sorted(boat_battles + pvp_battles)

            if len(all_battles) != stats_sum:
                LOG.warning("More battles logged than stats summary adds up to")
                continue

            sorted_battles: List[List[datetime.datetime]] = [[], [], [], []]

            for i in range(4):
                while all_battles and all_battles[0] < reset_times[i]:
                    sorted_battles[i].append(all_battles[0])
                    all_battles.pop(0)

            use_calculated_deck_usage = True

            for i, day_key in enumerate(day_keys):
                calculated_daily_usage = len(sorted_battles[i])

                if (calculated_daily_usage < user_data[day_key]) or (calculated_daily_usage > 4):
                    LOG.warning(log_message("Invalid calculated daily usage",
                                            calculated_daily_usage=calculated_daily_usage,
                                            api_daily_usage=user_data[day_key],
                                            day_key=day_key))
                    use_calculated_deck_usage = False
                    break

            if use_calculated_deck_usage:
                for i, day_key in enumerate(day_keys):
                    calculated_daily_usage = len(sorted_battles[i])

                    LOG.info(log_message("Correcting daily usage",
                                         prev=user_data[day_key],
                                         new=calculated_daily_usage,
                                         day_key=day_key))

                    query = (f"UPDATE river_race_user_data SET {day_key} = %s, last_check = last_check "
                             "WHERE clan_affiliation_id = %s AND river_race_id = %s")
                    cursor.execute(query, (calculated_daily_usage, clan_affiliation_id, river_race_id))

        elif deck_usage_sum > stats_sum:
            LOG.warning(log_message("Deck usage sum exceeds stats sum",
                                    clan_affiliation_id=clan_affiliation_id,
                                    river_race_id=river_race_id,
                                    deck_usage_sum=deck_usage_sum,
                                    stats_sum=stats_sum))

    database.commit()
    database.close()


##############################
#    _  ___      _           #
#   | |/ (_) ___| | _____    #
#   | ' /| |/ __| |/ / __|   #
#   | . \| | (__|   <\__ \   #
#   |_|\_\_|\___|_|\_\___/   #
#                            #
##############################

def kick_user(player_tag: str, clan_tag: str) -> bool:
    """Log a kick for a user.

    Args:
        player_tag: Tag of user to kick.
        clan_tag: Tag of clan to associate kick with.

    Returns:
        Whether the kick was successfully logged.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM users WHERE tag = %s", (player_tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return False

    user_id = query_result["id"]
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (clan_tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return False

    clan_id = query_result["id"]
    cursor.execute("INSERT INTO kicks (user_id, clan_id) VALUES (%s, %s)", (user_id, clan_id))
    database.commit()
    database.close()
    return True


def undo_kick(player_tag: str, clan_tag: str) -> Union[datetime.datetime, None]:
    """Delete the most recent kick logged for a user.

    Args:
        player_tag: Tag of user to undo kick for.
        clan_tag: Tag of clan to look for kicks from.

    Returns:
        Time of most recent kick that was removed, or None if no kicks were removed.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM users WHERE tag = %s", (player_tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return None

    user_id = query_result["id"]
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (clan_tag))
    query_result = cursor.fetchone()

    if query_result is None:
        database.close()
        return None

    clan_id = query_result["id"]
    cursor.execute("SELECT time FROM kicks WHERE user_id = %s AND clan_id = %s", (user_id, clan_id))
    kicks = [kick["time"] for kick in cursor]
    kicks.sort()

    if not kicks:
        database.close()
        return None

    cursor.execute("DELETE FROM kicks WHERE time = %s AND user_id = %s AND clan_id = %s", (kicks[-1], user_id, clan_id))
    database.commit()
    database.close()
    return kicks[-1]


def get_kicks(tag: str) -> Dict[str, KickData]:
    """Get a list of times a user was kicked.

    Args:
        tag: Tag of user to get kicks of.

    Returns:
        Dictionary mapping clan tags to data about a user's kicks from that clan.
    """
    primary_clans = get_primary_clans()
    kick_data: Dict[str, KickData] = {}

    for clan in primary_clans:
        data: KickData = {
            "tag": clan["tag"],
            "name": clan["name"],
            "kicks": []
        }
        kick_data[clan["tag"]] = data

    database, cursor = get_database_connection()
    cursor.execute("SELECT time, tag FROM kicks INNER JOIN clans ON kicks.clan_id = clans.id WHERE kicks.user_id =\
                    (SELECT id FROM users WHERE tag = %s)",
                   (tag))
    database.close()

    for kick in cursor:
        kick_data[kick["tag"]]["kicks"].append(kick["time"])

    for data in kick_data.values():
        data["kicks"].sort()

    return kick_data


###############################################################
#     _         _                        _   _                #
#    / \  _   _| |_ ___  _ __ ___   __ _| |_(_) ___  _ __     #
#   / _ \| | | | __/ _ \| '_ ` _ \ / _` | __| |/ _ \| '_ \    #
#  / ___ \ |_| | || (_) | | | | | | (_| | |_| | (_) | | | |   #
# /_/   \_\__,_|\__\___/|_| |_| |_|\__,_|\__|_|\___/|_| |_|   #
#                                                             #
###############################################################

def set_automated_routine(tag: str, routine: AutomatedRoutine, status: bool):
    """Update the status of an automated task for a primary clan.

    Args:
        tag: Tag of clan to change status for.
        routine: Which automated routine to update the status of.
        status: New status to set for the specified routine.
    """
    database, cursor = get_database_connection()
    query = f"UPDATE primary_clans SET {routine.value} = %s WHERE clan_id = (SELECT id FROM clans WHERE tag = %s)"
    cursor.execute(query, (status, tag))
    database.commit()
    database.close()


def set_participation_requirements(tag: str, strike_threshold: int):
    """Update a primary clan's participation requirements.
    
    Args:
        tag: Tag of clan to change participation requirements of.
        strike_threshold: Number of decks that must be used each war day.
    """
    database, cursor = get_database_connection()
    cursor.execute("UPDATE primary_clans SET strike_threshold = %s\
                    WHERE clan_id = (SELECT id FROM clans WHERE tag = %s)",
                   (strike_threshold, tag))
    database.commit()
    database.close()


#########################################
#    _____                       _      #
#   | ____|_  ___ __   ___  _ __| |_    #
#   |  _| \ \/ / '_ \ / _ \| '__| __|   #
#   | |___ >  <| |_) | (_) | |  | |_    #
#   |_____/_/\_\ .__/ \___/|_|   \__|   #
#              |_|                      #
#########################################

def get_file_path(name: str) -> str:
    """Get path of new spreadsheet file that should be created during export process.

    Args:
        name: Name of clan being exported.

    Returns:
        Path to new file.
    """
    if not os.path.exists(EXPORT_PATH):
        os.makedirs(EXPORT_PATH)

    files = [os.path.join(EXPORT_PATH, f) for f in os.listdir(EXPORT_PATH) if os.path.isfile(os.path.join(EXPORT_PATH, f))]
    files.sort(key=os.path.getmtime)

    if len(files) >= 5:
        os.remove(files[0])

    file_name = name.replace(" ", "_") + "_" + str(datetime.datetime.now().date()) + ".xlsx"
    new_path = os.path.join(EXPORT_PATH, file_name)

    return new_path


def export_clan_data(tag: str, name: str, active_only: bool, weeks: int) -> str:
    """Export relevant data about a clan to a spreadsheet.

    Args:
        tag: Tag of clan to export.
        name: Name of clan to export.
        active_only: Whether to only include active members of the clan or anyone with an affiliation to it.
        weeks: How many weeks to show stats for

    Returns:
        Path to spreadsheet.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    clean_up_database()
    add_unregistered_users(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    clan_id = cursor.fetchone()["id"]

    if active_only:
        cursor.execute("SELECT id FROM clan_affiliations WHERE clan_id = %s AND role IS NOT NULL", (clan_id))
    else:
        cursor.execute("SELECT id FROM clan_affiliations WHERE clan_id = %s", (clan_id))

    affiliation_id_list: List[int] = [user["id"] for user in cursor]
    path = get_file_path(name)
    workbook = xlsxwriter.Workbook(path)
    bold_format = workbook.add_format()
    bold_format.set_bold()

    # Users sheet
    users_sheet = workbook.add_worksheet("Players")
    users_headers = ["Player Name", "Player Tag", "Discord Name", "Clan Name", "Clan Tag",
                     "Clan Role", "Strikes", "Kicks", "Original Join Date", "Days In Clan", "RoyaleAPI"]
    users_sheet.write_row(0, 0, users_headers, bold_format)
    users_sheet.freeze_panes(1, 0)

    # Kicks sheet
    kicks_sheet = workbook.add_worksheet("Kicks")
    kicks_headers = ["Player Name", "Player Tag"]
    kicks_sheet.write_row(0, 0, kicks_headers, bold_format)
    kicks_sheet.freeze_panes(1, 0)

    # Data needed to create summary, stats, and deck usage sheets
    cursor.execute("SELECT id, season_id, week, start_time FROM river_races WHERE clan_id = %s ORDER BY season_id DESC, week DESC",
                   (clan_id))
    query_result = [race for race in cursor.fetchmany(size=weeks)]
    query_result.reverse()

    # Summary sheet
    summary_sheet = workbook.add_worksheet("Summary")
    summary_headers = ["Player Name", "Player Tag", "Discord Name", "Clan Role", "Strikes", "Original Join Date"]

    for river_race in query_result:
        summary_headers.append(f"S{river_race['season_id']}-W{river_race['week']}")

    summary_sheet.write_row(0, 0, summary_headers, bold_format)
    summary_sheet.freeze_panes(1, 0)

    # Stats/Deck Usage sheets
    river_race_list: List[Tuple[int, Worksheet, Worksheet]] = []

    stats_headers = ["Player Name", "Player Tag", "Medals", "Decks Used", "Tracked Since",
                     "Regular Wins", "Regular Losses", "Regular Win Rate",
                     "Special Wins", "Special Losses", "Special Win Rate",
                     "Duel Match Wins", "Duel Match Losses", "Duel Match Win Rate",
                     "Duel Series Wins", "Duel Series Losses", "Duel Series Win Rate",
                     "Boat Attack Wins", "Boat Attack Losses", "Boat Attack Win Rate",
                     "Combined PvP Wins", "Combined PvP Losses", "Combined PvP Win Rate"]

    for river_race in query_result:
        stats_sheet_name = f"S{river_race['season_id']}-W{river_race['week']} Stats"
        stats_sheet = workbook.add_worksheet(stats_sheet_name)
        stats_sheet.write_row(0, 0, stats_headers, bold_format)
        stats_sheet.freeze_panes(1, 0)

        history_sheet_name = f"S{river_race['season_id']}-W{river_race['week']} History"
        history_sheet = workbook.add_worksheet(history_sheet_name)
        history_headers = ["Player Name", "Player Tag"]
        history_header_date = river_race["start_time"]

        for _ in range(7):
            history_headers.append(history_header_date.strftime("%a, %b %d"))
            history_header_date += datetime.timedelta(days=1)

        history_sheet.write_row(0, 0, history_headers, bold_format)
        history_sheet.freeze_panes(1, 0)
        river_race_list.append((river_race["id"], stats_sheet, history_sheet))

    all_time_stats_sheet = workbook.add_worksheet("All Time")
    all_time_stats_headers = ["Player Name", "Player Tag",
                              "Regular Wins", "Regular Losses", "Regular Win Rate",
                              "Special Wins", "Special Losses", "Special Win Rate",
                              "Duel Match Wins", "Duel Match Losses", "Duel Match Win Rate",
                              "Duel Series Wins", "Duel Series Losses", "Duel Series Win Rate",
                              "Boat Attack Wins", "Boat Attack Losses", "Boat Attack Win Rate",
                              "Combined PvP Wins", "Combined PvP Losses", "Combined PvP Win Rate"]
    all_time_stats_sheet.write_row(0, 0, all_time_stats_headers, bold_format)
    all_time_stats_sheet.freeze_panes(1, 0)

    # Write user data
    for row, clan_affiliation_id in enumerate(affiliation_id_list, start=1):
        cursor.execute("SELECT\
                            users.name AS player_name,\
                            users.tag AS player_tag,\
                            clans.name AS clan_name,\
                            clans.tag AS clan_tag,\
                            discord_name,\
                            role,\
                            strikes,\
                            first_joined\
                        FROM users INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                        INNER JOIN clans ON clan_affiliations.clan_id = clans.id\
                        WHERE clan_affiliations.id = %s",
                       (clan_affiliation_id))
        user_data = cursor.fetchone()

        if user_data["role"]:
            user_data["role"] = user_data["role"].capitalize()

        kick_data = get_kicks(user_data["player_tag"])
        kicks = kick_data[tag]["kicks"]

        days = time_in_clan(user_data["player_tag"], [tag]).days

        # Users sheet data
        user_row = [user_data["player_name"], user_data["player_tag"], user_data["discord_name"], user_data["clan_name"],
                    user_data["clan_tag"], user_data["role"], user_data["strikes"], len(kicks),
                    user_data["first_joined"].strftime("%Y-%m-%d %H:%M"), days, clash_utils.royale_api_url(user_data["player_tag"])]
        users_sheet.write_row(row, 0, user_row)

        # Kicks sheet data
        kicks_row = [user_data["player_name"], user_data["player_tag"]]
        kicks_row.extend([kick.strftime("%Y-%m-%d") for kick in kicks])
        kicks_sheet.write_row(row, 0, kicks_row)

        # Summary sheet data
        summary_row = [user_data["player_name"], user_data["player_tag"], user_data["discord_name"], user_data["role"],
                       user_data["strikes"], user_data["first_joined"].strftime("%Y-%m-%d %H:%M")]

        # Stats/Deck Usage data
        for river_race_id, stats_sheet, history_sheet in river_race_list:
            cursor.execute("SELECT * FROM river_race_user_data WHERE clan_affiliation_id = %s AND river_race_id = %s",
                           (clan_affiliation_id, river_race_id))
            race_data = cursor.fetchone()
            history_row = [user_data["player_name"], user_data["player_tag"]]
            stats_row = [user_data["player_name"], user_data["player_tag"]]

            if race_data is None:
                summary_row.append("-")
                history_row.extend(["-"] * 7)
                stats_row.extend([None] * 21)
            else:
                # History
                for key in ["day_1", "day_2", "day_3", "day_4", "day_5", "day_6", "day_7"]:
                    usage = race_data[key]

                    if usage is None:
                        usage = "-"

                    history_row.append(usage)

                # Stats
                if race_data["tracked_since"] is None:
                    tracked_since = None
                else:
                    tracked_since = race_data["tracked_since"].strftime("%Y-%m-%d %H:%M")

                stats_row.extend([race_data["medals"], 0, tracked_since])
                pvp_wins = 0
                pvp_losses = 0
                decks_used = 0

                for key in ["regular", "special", "duel"]:
                    wins = race_data[f"{key}_wins"]
                    losses = race_data[f"{key}_losses"]
                    total = wins + losses
                    decks_used += total
                    pvp_wins += wins
                    pvp_losses += losses
                    win_rate = 0 if total == 0 else round(wins / total, 4)
                    stats_row.extend([wins, losses, win_rate])

                for key in ["series", "boat"]:
                    wins = race_data[f"{key}_wins"]
                    losses = race_data[f"{key}_losses"]
                    total = wins + losses
                    win_rate = 0 if total == 0 else round(wins / total, 4)
                    stats_row.extend([wins, losses, win_rate])

                    if key == "boat":
                        decks_used += total

                pvp_total = pvp_wins + pvp_losses
                combined_win_rate = 0 if pvp_total == 0 else round(pvp_wins / pvp_total, 4)
                stats_row.extend([pvp_wins, pvp_losses, combined_win_rate])
                stats_row[3] = decks_used
                summary_row.append(decks_used)

            history_sheet.write_row(row, 0, history_row)
            stats_sheet.write_row(row, 0, stats_row)

        summary_sheet.write_row(row, 0, summary_row)

        # All time stats
        cursor.execute("SELECT * FROM river_race_user_data WHERE clan_affiliation_id = %s", (clan_affiliation_id))
        all_time_stats = [0] * 18

        for race_data in cursor:
            all_time_stats[0] += race_data["regular_wins"]
            all_time_stats[1] += race_data["regular_losses"]
            all_time_stats[3] += race_data["special_wins"]
            all_time_stats[4] += race_data["special_losses"]
            all_time_stats[6] += race_data["duel_wins"]
            all_time_stats[7] += race_data["duel_losses"]
            all_time_stats[9] += race_data["series_wins"]
            all_time_stats[10] += race_data["series_losses"]
            all_time_stats[12] += race_data["boat_wins"]
            all_time_stats[13] += race_data["boat_losses"]

        all_time_stats[15] = all_time_stats[0] + all_time_stats[3] + all_time_stats[6]  # PvP wins
        all_time_stats[16] = all_time_stats[1] + all_time_stats[4] + all_time_stats[7]  # PvP losses

        # Calculate win rates
        for i in [2, 5, 8, 11, 14, 17]:
            total = all_time_stats[i-2] + all_time_stats[i-1]
            all_time_stats[i] = 0 if total == 0 else round(all_time_stats[i-2] / total, 4)

        all_time_stats_row = [user_data["player_name"], user_data["player_tag"]] + all_time_stats
        all_time_stats_sheet.write_row(row, 0, all_time_stats_row)

    # Autofit all sheets
    users_sheet.autofit()
    kicks_sheet.autofit()
    summary_sheet.autofit()

    for _, stats_sheet, history_sheet in river_race_list:
        stats_sheet.autofit()
        history_sheet.autofit()
        all_time_stats_sheet.autofit()

    database.close()
    workbook.close()
    return path


def export_all_clan_data(primary_only: bool, active_only: bool) -> str:
    """Export relevant data of members in the database.

    Args:
        primary_only: Whether to only include members in primary clans or all database users.
        active_only: Whether to only include active members of the primary clans or anyone with an affiliation to one. Has no effect
                     if primary_only is False.

    Returns:
        Path to spreadsheet.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    clean_up_database()
    primary_clans = get_primary_clans()
    clan_tags = [primary_clan["tag"] for primary_clan in primary_clans]

    for clan in primary_clans:
        add_unregistered_users(clan["tag"])

    database, cursor = get_database_connection()

    if primary_only:
        if active_only:
            cursor.execute("SELECT user_id AS id FROM clan_affiliations\
                            WHERE clan_id IN (SELECT clan_id FROM primary_clans) AND role IS NOT NULL")
        else:
            cursor.execute("SELECT DISTINCT user_id AS id FROM clan_affiliations\
                            WHERE clan_id IN (SELECT clan_id FROM primary_clans)")
    else:
        cursor.execute("SELECT id FROM users")

    user_id_list: List[int] = [user["id"] for user in cursor]

    if primary_only:
        path = get_file_path("primary_clans")
    else:
        path = get_file_path("all_users")

    workbook = xlsxwriter.Workbook(path)
    bold_format = workbook.add_format()
    bold_format.set_bold()

    # Users sheet
    users_sheet = workbook.add_worksheet("Players")
    users_headers = ["Player Name", "Player Tag", "Discord Name", "Clan Name", "Clan Tag",
                     "Clan Role", "Strikes", "Kicks", "Original Join Date", "Days In Clan Family", "RoyaleAPI"]
    users_sheet.write_row(0, 0, users_headers, bold_format)
    users_sheet.freeze_panes(1, 0)

    # Kicks sheets
    kicks_sheets = {}
    kicks_headers = ["Player Name", "Player Tag"]

    for clan in primary_clans:
        sheet = workbook.add_worksheet(f"{clan['name']} Kicks")
        sheet.write_row(0, 0, kicks_headers, bold_format)
        sheet.freeze_panes(1, 0)
        kicks_sheets[clan["tag"]] = sheet

    # Stats sheets
    stats_sheets: List[Tuple[int, Worksheet]] = []
    stats_headers = ["Player Name", "Player Tag",
                     "Regular Wins", "Regular Losses", "Regular Win Rate",
                     "Special Wins", "Special Losses", "Special Win Rate",
                     "Duel Match Wins", "Duel Match Losses", "Duel Match Win Rate",
                     "Duel Series Wins", "Duel Series Losses", "Duel Series Win Rate",
                     "Boat Attack Wins", "Boat Attack Losses", "Boat Attack Win Rate",
                     "Combined PvP Wins", "Combined PvP Losses", "Combined PvP Win Rate"]

    for clan in primary_clans:
        stats_sheet = workbook.add_worksheet(f"{clan['name']} Stats")
        stats_sheet.write_row(0, 0, stats_headers, bold_format)
        stats_sheet.freeze_panes(1, 0)
        stats_sheets.append((clan["id"], stats_sheet))

    combined_stats_sheet = workbook.add_worksheet("Combined Stats")
    combined_stats_sheet.write_row(0, 0, stats_headers, bold_format)
    combined_stats_sheet.freeze_panes(1, 0)

    # Write user data
    for row, user_id in enumerate(user_id_list, start=1):
        cursor.execute("SELECT name AS player_name, tag AS player_tag, discord_name, strikes FROM users WHERE id = %s", (user_id))
        user_data = cursor.fetchone()

        cursor.execute("SELECT name AS clan_name, tag AS clan_tag, role, first_joined FROM clan_affiliations\
                        INNER JOIN clans ON clan_affiliations.clan_id = clans.id\
                        WHERE clan_affiliations.user_id = %s AND role IS NOT NULL",
                       (user_id))
        query_result = cursor.fetchone()

        if query_result is None:
            user_data["clan_name"] = None
            user_data["clan_tag"] = None
            user_data["role"] = ""
            user_data["first_joined"] = None
        else:
            user_data.update(query_result)
            user_data["first_joined"] = user_data["first_joined"].strftime("%Y-%m-%d %H:%M")

        kicks = get_kicks(user_data["player_tag"])
        total_kicks = 0

        for kick_data in kicks.values():
            total_kicks += len(kick_data["kicks"])

        total_days = time_in_clan(user_data["player_tag"], clan_tags).days

        # Users sheet data
        user_row = [user_data["player_name"], user_data["player_tag"], user_data["discord_name"], user_data["clan_name"],
                    user_data["clan_tag"], user_data["role"].capitalize(), user_data["strikes"], total_kicks,
                    user_data["first_joined"], total_days, clash_utils.royale_api_url(user_data["player_tag"])]
        users_sheet.write_row(row, 0, user_row)

        # Kicks sheets data
        for clan_tag, kick_data in kicks.items():
            kicks_row = [user_data["player_name"], user_data["player_tag"]]
            kicks_row.extend([kick.strftime("%Y-%m-%d") for kick in kick_data["kicks"]])
            kicks_sheets[clan_tag].write_row(row, 0, kicks_row)

        # Stats sheets data
        combined_stats = [0] * 18

        for clan_id, sheet in stats_sheets:
            stats = [0] * 18
            cursor.execute("SELECT * FROM river_race_user_data\
                            WHERE clan_affiliation_id = (SELECT id FROM clan_affiliations WHERE user_id = %s AND clan_id = %s)",
                           (user_id, clan_id))

            for race_data in cursor:
                stats[0] += race_data["regular_wins"]
                stats[1] += race_data["regular_losses"]
                stats[3] += race_data["special_wins"]
                stats[4] += race_data["special_losses"]
                stats[6] += race_data["duel_wins"]
                stats[7] += race_data["duel_losses"]
                stats[9] += race_data["series_wins"]
                stats[10] += race_data["series_losses"]
                stats[12] += race_data["boat_wins"]
                stats[13] += race_data["boat_losses"]

            stats[15] = stats[0] + stats[3] + stats[6]  # PvP wins
            stats[16] = stats[1] + stats[4] + stats[7]  # PvP losses

            # Add non win-rate values to the combined stats. Every third index is a win rate so skip those.
            for i in range(18):
                if i % 3 != 2:
                    combined_stats[i] += stats[i]

            # Calculate win rates for performance in individual clan.
            for i in [2, 5, 8, 11, 14, 17]:
                total = stats[i-2] + stats[i-1]
                stats[i] = 0 if total == 0 else round(stats[i-2] / total, 4)

            stats_row = [user_data["player_name"], user_data["player_tag"]] + stats
            sheet.write_row(row, 0, stats_row)

        # Calculate win rates for performance across all primary clans.
        for i in [2, 5, 8, 11, 14, 17]:
            total = combined_stats[i-2] + combined_stats[i-1]
            combined_stats[i] = 0 if total == 0 else round(combined_stats[i-2] / total, 4)

        combined_stats_row = [user_data["player_name"], user_data["player_tag"]] + combined_stats
        combined_stats_sheet.write_row(row, 0, combined_stats_row)

    # Autofit all sheets
    users_sheet.autofit()

    for kicks_sheet in kicks_sheets.values():
        kicks_sheet.autofit()

    for _, stats_sheet in stats_sheets:
        stats_sheet.autofit()

    combined_stats_sheet.autofit()

    database.close()
    workbook.close()
    return path


def fix_deck_ids():
    """Workaround to fixing decks in database that incorrectly calculated relative card levels due to a bug in Supercell's API."""
    database, cursor = get_database_connection()

    old_decks_query = """
        SELECT deck_id,
               Group_concat(card_id ORDER BY card_id)    AS card_ids,
               Group_concat(card_level ORDER BY card_id) AS card_levels
        FROM   deck_cards
        WHERE  deck_id NOT IN (SELECT deck_id
                               FROM   deck_cards
                               WHERE  deck_id IN (SELECT deck_id
                                                  FROM   pvp_battles
                                                  WHERE  time > Date_sub(Now(), INTERVAL 14 day))
                                       OR deck_id IN (SELECT opp_deck_id
                                                      FROM   pvp_battles
                                                      WHERE  time > Date_sub(Now(), INTERVAL 14 day))
                               GROUP  BY deck_id)
        GROUP  BY deck_id
    """

    new_decks_query = """
        SELECT deck_id,
               Group_concat(card_id ORDER BY card_id)    AS card_ids,
               Group_concat(card_level ORDER BY card_id) AS card_levels
        FROM   deck_cards
        WHERE  deck_id IN (SELECT deck_id
                           FROM   pvp_battles
                           WHERE  time > Date_sub(Now(), INTERVAL 14 day))
                OR deck_id IN (SELECT opp_deck_id
                               FROM   pvp_battles
                               WHERE  time > Date_sub(Now(), INTERVAL 14 day))
        GROUP  BY deck_id
    """

    cursor.execute(old_decks_query)
    query_result = cursor.fetchall()
    old_decks: Dict[Tuple[str, str], int] = {}

    for deck in query_result:
        key = (deck["card_ids"], deck["card_levels"])
        old_decks[key] = deck["deck_id"]

    cursor.execute(new_decks_query)
    query_result = cursor.fetchall()

    for deck in query_result:
        incorrect_levels = deck["card_levels"]
        corrected_levels = ",".join([str(int(card_id) - 1) for card_id in incorrect_levels.split(",")])
        key = (deck["card_ids"], corrected_levels)

        if key in old_decks:
            print(f"Replacing {deck['deck_id']} with {old_decks[key]}")
            cursor.execute("UPDATE pvp_battles SET deck_id = %s WHERE deck_id = %s", (old_decks[key], deck["deck_id"]))
            cursor.execute("UPDATE pvp_battles SET opp_deck_id = %s WHERE opp_deck_id = %s", (old_decks[key], deck["deck_id"]))
            cursor.execute("DELETE FROM deck_cards WHERE deck_id = %s", (deck["deck_id"]))
        else:
            print(f"Altering levels on deck {deck['deck_id']}")
            cursor.execute("UPDATE deck_cards SET card_level = card_level - 1 WHERE deck_id = %s", (deck["deck_id"]))

    database.commit()
    database.close()
