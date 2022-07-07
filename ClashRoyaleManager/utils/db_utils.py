"""Functions that interface with the database."""

import datetime
import os
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
    BattleStats,
    ClanRole,
    ClanStrikeInfo,
    ClashData,
    DatabaseReport,
    DatabaseRiverRaceClan,
    KickData,
    PrimaryClan,
    ReminderTime,
    SpecialChannel,
    SpecialRole,
    StrikeType,
)
from utils.exceptions import GeneralAPIError

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
                else:
                    cursor.execute("INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check)\
                                    VALUES (%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s)\
                                    ON DUPLICATE KEY UPDATE clan_affiliation_id = clan_affiliation_id",
                                   clash_data)

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


def update_user(tag: str):
    """Get a user's most up to date information and update their name and clan affiliation.

    Args:
        tag: Tag of user to update.

    Raises:
        GeneralAPIError: Something went wrong with the request.
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

    cursor.execute("UPDATE users SET name = %(name)s, needs_update = TRUE WHERE id = %(user_id)s", clash_data)

    database.commit()
    database.close()
    update_clan_affiliation(clash_data)


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

    LOG.info("Database clean up complete")


def set_reminder_time(discord_id: int, reminder_time: ReminderTime):
    """Update a user's reminder time.

    Args:
        discord_id: Discord ID of user to update.
        reminder_time: New preferred time to receive reminders.
    """
    database, cursor = get_database_connection()
    affected_rows = cursor.execute("UPDATE users SET reminder_time = %s WHERE discord_id = %s", (reminder_time.value, discord_id))
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
            "strike_type": StrikeType(clan["strike_type"]),
            "strike_threshold": clan["strike_threshold"],
            "discord_channel_id": clan["discord_channel_id"]
        }
        primary_clans.append(clan_data)

    return primary_clans


def get_primary_clans_enum() -> Enum:
    database, cursor = get_database_connection()
    cursor.execute("SELECT clans.tag, clans.name FROM clans INNER JOIN primary_clans ON clans.id = primary_clans.clan_id")
    database.close()
    return Enum("PrimaryClan", {clan["name"]: clan["tag"] for clan in cursor})


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


def get_all_clan_affiliations() -> List[Tuple[str, str, str, ClanRole]]:
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

    cursor.execute("SELECT tag, name FROM users WHERE id NOT IN (SELECT user_id FROM clan_affiliations)")

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


def get_most_recent_reset_time(tag: str) -> datetime.datetime:
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
    add_unregistered_users(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_race_user_data SET last_check = %s WHERE river_race_id = %s", (current_time, river_race_id))
    cursor.execute("UPDATE river_race_user_data SET tracked_since = %s WHERE river_race_id = %s AND\
                    clan_affiliation_id IN (SELECT id FROM clan_affiliations WHERE clan_id = %s AND role IS NOT NULL)",
                   (current_time, river_race_id, clan_id))

    try:
        update_river_race_clans(tag)
    except GeneralAPIError:
        LOG.warning(f"Unable to get clans during battle day preparations for clan {tag}")

    database.commit()
    database.close()


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


def record_deck_usage_today(tag: str, weekday: int, deck_usage: Dict[str, int]):
    """Log daily deck usage for each member of a clan and record reset time.

    Args:
        tag: Tag of clan to log deck usage for.
        weekday: Which day usage is being logged on.
        reset_time: Time that daily reset occurred.
        deck_usage: Dictionary of player tags mapped to their decks used today in the specified clan.
    """
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(tag)

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

    last_check = get_last_check(tag)
    update_usage_query = (f"INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check, {day_key}) "
                          f"VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE {day_key} = %s, last_check = last_check")

    for player_tag, decks_used in deck_usage.items():
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

        clan_affiliation_id = query_result["id"]
        cursor.execute(update_usage_query, (clan_affiliation_id, river_race_id, last_check, decks_used, decks_used))

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


def record_battle_day_stats(stats: List[Tuple[BattleStats, int]]):
    """Update users' Battle Day stats with their latest matches.

    Args:
        stats: List of tuples of users' stats and medal counts.
    """
    if not stats:
        return

    clan_tag = stats[0][0]["clan_tag"]
    river_race_id, clan_id, _, _ = get_clan_river_race_ids(clan_tag)

    if river_race_id is None:
        LOG.warning(log_message("Missing river_races entry", clan_tag=clan_tag))
        return

    database, cursor = get_database_connection()

    for user_stats, medals in stats:
        user_stats["medals"] = medals
        user_stats["river_race_id"] = river_race_id
        user_stats["clan_id"] = clan_id
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

    database.commit()
    database.close()


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
    database, cursor = get_database_connection()
    cursor.execute("INSERT INTO seasons VALUES (DEFAULT, DEFAULT)")
    database.commit()
    database.close()


def prepare_for_river_race(tag: str):
    """Insert a new river_race entry for the specified clan, along with a new set of five river_race_clans entries.

    Args:
        tag: Tag of clan to create entries for.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    clan_id = cursor.fetchone()["id"]
    cursor.execute("SELECT MAX(id) AS id FROM seasons")
    season_id = cursor.fetchone()["id"]

    try:
        river_race_info = clash_utils.get_current_river_race_info(tag)

        if clash_utils.is_first_day_of_season():
            river_race_info["week"] = 1
            river_race_info["colosseum_week"] = False
            river_race_info["completed_saturday"] = False
    except GeneralAPIError:
        LOG.warning(f"Unable to get current river race info for {tag}. Creating placeholder River Race entry.")
        river_race_info = {
            "week": 0,
            "start_time": datetime.datetime.fromisoformat("1970-01-01 00:00:00.000"),
            "colosseum_week": False,
            "completed_saturday": False,
            "clans": []
        }

    river_race_info["clan_id"] = clan_id
    river_race_info["season_id"] = season_id

    cursor.execute("INSERT INTO river_races (clan_id, season_id, week, start_time, colosseum_week, completed_saturday)\
                    VALUES (%(clan_id)s, %(season_id)s, %(week)s, %(start_time)s, %(colosseum_week)s, %(completed_saturday)s)",
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


########################################
#    ____  _        _ _                #
#   / ___|| |_ _ __(_) | _____  ___    #
#   \___ \| __| '__| | |/ / _ \/ __|   #
#    ___) | |_| |  | |   <  __/\__ \   #
#   |____/ \__|_|  |_|_|\_\___||___/   #
#                                      #
########################################

def get_strike_determination_data(tag: str) -> ClanStrikeInfo:
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

    cursor.execute("SELECT strike_type, strike_threshold FROM primary_clans WHERE clan_id = %s", (clan_id))
    query_result = cursor.fetchone()
    strike_info["strike_type"] = StrikeType(query_result["strike_type"])
    strike_info["strike_threshold"] = query_result["strike_threshold"]

    cursor.execute("SELECT completed_saturday, day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    strike_info["completed_saturday"] = query_result["completed_saturday"]
    strike_info["reset_times"] = [query_result[day_key] for day_key in ["day_4", "day_5", "day_6", "day_7"]]

    cursor.execute("SELECT discord_id, name, tag, tracked_since, medals, day_4, day_5, day_6, day_7 FROM river_race_user_data\
                    INNER JOIN clan_affiliations ON river_race_user_data.clan_affiliation_id = clan_affiliations.id\
                    INNER JOIN users ON clan_affiliations.user_id = users.id\
                    WHERE river_race_id = %s AND tracked_since IS NOT NULL",
                   (river_race_id))
    database.close()
    strike_info["users"] = {}

    for user in cursor:
        strike_info["users"][user["tag"]] = {
            "discord_id": user["discord_id"],
            "name": user["name"],
            "tracked_since": user["tracked_since"],
            "medals": user["medals"],
            "deck_usage": [user[day_key] for day_key in ["day_4", "day_5", "day_6", "day_7"]]
        }

    return strike_info


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


def set_participation_requirements(tag: str, strike_type: StrikeType, strike_threshold: int):
    """Update a primary clan's participation requirements.
    
    Args:
        tag: Tag of clan to change participation requirements of.
        strike_type: What kind of participation requirement to change to.
        strike_threshold: Number of medals/decks needed for the specified strike type.
    """
    database, cursor = get_database_connection()
    cursor.execute("UPDATE primary_clans SET strike_type = %s, strike_threshold = %s\
                    WHERE clan_id = (SELECT id FROM clans WHERE tag = %s)",
                   (strike_type.value, strike_threshold, tag))
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
    path = "export_data"

    if not os.path.exists(path):
        os.makedirs(path)

    files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    files.sort(key=os.path.getmtime)

    if len(files) >= 5:
        os.remove(files[0])

    file_name = name.replace(" ", "_") + "_" + str(datetime.datetime.now().date()) + ".xlsx"
    new_path = os.path.join(path, file_name)

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

    # Users sheet
    users_sheet = workbook.add_worksheet("Players")
    users_headers = ["Player Name", "Player Tag", "Discord Name", "Clan Name", "Clan Tag",
                     "Clan Role", "Strikes", "Kicks", "Join Date", "RoyaleAPI"]
    users_sheet.write_row(0, 0, users_headers)

    # Kicks sheet
    kicks_sheet = workbook.add_worksheet("Kicks")
    kicks_headers = ["Player Name", "Player Tag"]
    kicks_sheet.write_row(0, 0, kicks_headers)

    # Stats/Deck Usage sheets
    cursor.execute("SELECT id, season_id, week, start_time FROM river_races WHERE clan_id = %s ORDER BY season_id DESC, week DESC",
                   (clan_id))
    query_result = [race for race in cursor.fetchmany(size=weeks)]
    query_result.reverse()
    river_race_list: List[Tuple[int, Worksheet, Worksheet]] = []

    stats_headers = ["Player Name", "Player Tag", "Medals", "Decks Used", "Tracked Since",
                     "Regular Wins", "Regular Losses", "Regular Win Rate",
                     "Special Wins", "Special Losses", "Special Win Rate",
                     "Duel Match Wins", "Duel Match Losses", "Duel Match Win Rate",
                     "Duel Series Wins", "Duel Series Losses", "Duel Series Win Rate",
                     "Boat Attack Wins", "Boat Attack Losses", "Boat Attack Win Rate",
                     "Combined PvP Wins", "Combined PvP Losses", "Combined PvP Win Rate"]

    for river_race in query_result:
        stats_sheet_name = f"{river_race['season_id']}-{river_race['week']} Stats"
        stats_sheet = workbook.add_worksheet(stats_sheet_name)
        stats_sheet.write_row(0, 0, stats_headers)

        history_sheet_name = f"{river_race['season_id']}-{river_race['week']} History"
        history_sheet = workbook.add_worksheet(history_sheet_name)
        history_headers = ["Player Name", "Player Tag"]
        history_header_date = river_race["start_time"]

        for _ in range(7):
            history_headers.append(history_header_date.strftime("%a, %b %d"))
            history_header_date += datetime.timedelta(days=1)

        history_sheet.write_row(0, 0, history_headers)
        river_race_list.append((river_race["id"], stats_sheet, history_sheet))

    all_time_stats_sheet = workbook.add_worksheet("All Time")
    all_time_stats_headers = ["Player Name", "Player Tag",
                              "Regular Wins", "Regular Losses", "Regular Win Rate",
                              "Special Wins", "Special Losses", "Special Win Rate",
                              "Duel Match Wins", "Duel Match Losses", "Duel Match Win Rate",
                              "Duel Series Wins", "Duel Series Losses", "Duel Series Win Rate",
                              "Boat Attack Wins", "Boat Attack Losses", "Boat Attack Win Rate",
                              "Combined PvP Wins", "Combined PvP Losses", "Combined PvP Win Rate"]
    all_time_stats_sheet.write_row(0, 0, all_time_stats_headers)

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

        # Users sheet data
        user_row = [user_data["player_name"], user_data["player_tag"], user_data["discord_name"], user_data["clan_name"],
                    user_data["clan_tag"], user_data["role"], user_data["strikes"], len(kicks),
                    user_data["first_joined"].strftime("%Y-%m-%d %H:%M"), clash_utils.royale_api_url(user_data["player_tag"])]
        users_sheet.write_row(row, 0, user_row)

        # Kicks sheet data
        kicks_row = [user_data["player_name"], user_data["player_tag"]]
        kicks_row.extend([kick.strftime("%Y-%m-%d") for kick in kicks])
        kicks_sheet.write_row(row, 0, kicks_row)

        # Stats/Deck Usage data
        for river_race_id, stats_sheet, history_sheet in river_race_list:
            cursor.execute("SELECT * FROM river_race_user_data WHERE clan_affiliation_id = %s AND river_race_id = %s",
                           (clan_affiliation_id, river_race_id))
            race_data = cursor.fetchone()
            history_row = [user_data["player_name"], user_data["player_tag"]]
            stats_row = [user_data["player_name"], user_data["player_tag"]]

            if race_data is None:
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

            history_sheet.write_row(row, 0, history_row)
            stats_sheet.write_row(row, 0, stats_row)

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

    # Users sheet
    users_sheet = workbook.add_worksheet("Players")
    users_headers = ["Player Name", "Player Tag", "Discord Name", "Clan Name", "Clan Tag",
                     "Clan Role", "Strikes", "Kicks", "Join Date", "RoyaleAPI"]
    users_sheet.write_row(0, 0, users_headers)

    # Kicks sheets
    kicks_sheets = {}
    kicks_headers = ["Player Name", "Player Tag"]

    for clan in primary_clans:
        sheet = workbook.add_worksheet(f"{clan['name']} Kicks")
        sheet.write_row(0, 0, kicks_headers)
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
        stats_sheet.write_row(0, 0, stats_headers)
        stats_sheets.append((clan["id"], stats_sheet))

    combined_stats_sheet = workbook.add_worksheet("Combined Stats")
    combined_stats_sheet.write_row(0, 0, stats_headers)

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

        # Users sheet data
        user_row = [user_data["player_name"], user_data["player_tag"], user_data["discord_name"], user_data["clan_name"],
                    user_data["clan_tag"], user_data["role"].capitalize(), user_data["strikes"], total_kicks,
                    user_data["first_joined"], clash_utils.royale_api_url(user_data["player_tag"])]
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

    database.close()
    workbook.close()
    return path
