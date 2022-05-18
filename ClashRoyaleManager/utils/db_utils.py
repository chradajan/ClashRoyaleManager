"""Functions that interface with the database."""

import datetime
from typing import Dict, List, Optional, Set, Tuple, Union

import discord
import pymysql

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
    BattleStats,
    ClanRole,
    ClashData,
    DatabaseRiverRaceClan,
    PrimaryClan,
    SpecialChannel,
    SpecialRole,
    StrikeCriteria,
)
from utils.exceptions import GeneralAPIError

def get_database_connection() -> Tuple[pymysql.Connection, pymysql.cursors.DictCursor]:
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
            clash_data["river_race_id"], _, _, _ = get_current_clan_river_race_ids(clash_data["clan_tag"])

            if clash_data["river_race_id"] is not None:
                clash_data["last_check"] = get_last_check(clash_data["clan_tag"])
                cursor.execute("INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check) VALUES\
                                (%(clan_affiliation_id)s, %(river_race_id)s, %(last_check)s)\
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


def get_user_in_database(search_key: Union[int, str]) -> List[Tuple[str, str, str]]:
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
            "strike_type": StrikeCriteria(clan["strike_type"]),
            "strike_threshold": clan["strike_threshold"]
        }
        primary_clans.append(clan_data)

    return primary_clans


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


def get_current_clan_river_race_ids(tag: str) -> Tuple[int, int, int, int]:
    """Get a clan's current River Race entry id, clan_id, season_id, and week.

    Args:
        tag: Tag of clan to get IDs of.

    Returns:
        Tuple of id, clan_id, season_id, and week of most recent River Race entry of specified clan, or None if no entry exists.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT id, clan_id, season_id, week FROM river_races WHERE\
                    clan_id = (SELECT id FROM clans WHERE tag = %s) AND season_id = (SELECT MAX(id) FROM seasons)",
                   (tag))
    query_result = cursor.fetchall()
    query_result.sort(key=lambda x: x["week"], reverse=True)
    database.close()

    river_race_id = None
    clan_id = None
    season_id = None
    week = None

    if query_result is not None:
        most_recent_river_race = query_result[0]
        river_race_id = most_recent_river_race["id"]
        clan_id = most_recent_river_race["clan_id"]
        season_id = most_recent_river_race["season_id"]
        week = most_recent_river_race["week"]

    return (river_race_id, clan_id, season_id, week)


def get_most_recent_reset_time(tag: str) -> datetime.datetime:
    """Get the most recent daily reset time for the specified clan.

    Args:
        tag: Tag of clan to get latest daily reset time for.

    Returns:
        Most recent daily reset time, or None if no resets are currently logged.
    """
    river_race_id, _, _, _ = get_current_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT day_1, day_2, day_3, day_4, day_5, day_6, day_7 FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    reset_times = sorted(query_result.values())
    return reset_times[-1] if reset_times else None


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
    river_race_id, _, _, _ = get_current_clan_river_race_ids(tag)
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
    river_race_id, _, _, _ = get_current_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_races SET last_check = CURRENT_TIMESTAMP WHERE id = %s", (river_race_id))
    cursor.execute("SELECT last_check FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.commit()
    database.close()
    return query_result["last_check"]


def is_colosseum_week(tag: str) -> bool:
    """Check if it's currently a Colosseum week.

    Args:
        tag: Tag of clan to check.

    Returns:
        Whether it's currently Colosseum week.
    """
    river_race_id, _, _, _ = get_current_clan_river_race_ids(tag)
    database, cursor = get_database_connection()
    cursor.execute("SELECT colosseum_week FROM river_races WHERE id = %s", (river_race_id))
    query_result = cursor.fetchone()
    database.close()
    return query_result["colosseum_week"]


def prepare_for_battle_days(tag: str):
    """Make necessary preparations to start tracking for upcoming Battle Days.

    Args:
        tag: Tag of clan to prepare for.
    """
    river_race_id, clan_id, season_id, _ = get_current_clan_river_race_ids(tag)
    current_time = set_last_check(tag)
    add_unregistered_users(tag)
    database, cursor = get_database_connection()
    cursor.execute("UPDATE river_race_user_data SET last_check = %s WHERE river_race_id = %s", (current_time, river_race_id))

    try:
        clans_in_race = clash_utils.get_clans_in_race(tag, False)

        for clan_tag, clan in clans_in_race.items():
            cursor.execute("UPDATE river_race_clans SET current_race_medals = 0, current_race_total_decks = %s\
                            WHERE clan_id = %s AND season_id = %s AND tag = %s",
                           (clan["total_decks_used"], clan_id, season_id, clan_tag))
    except GeneralAPIError:
        LOG.warning(f"Unable to get clans during battle day preparations for clan {tag}")

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
    river_race_id, clan_id, _, _ = get_current_clan_river_race_ids(tag)

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
    update_usage_query = f"INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check, {day_key})\
                        VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE {day_key} = %s, last_check = last_check"

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
    river_race_id, _, _, _ = get_current_clan_river_race_ids(tag)

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
    river_race_id, clan_id, _, _ = get_current_clan_river_race_ids(clan_tag)

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
    _, clan_id, season_id, _ = get_current_clan_river_race_ids(tag)
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


def prepare_for_river_race(tag: str, force: bool=False):
    """Insert a new river_race entry for the specified clan, along with a new set of five river_race_clans entries.

    Args:
        tag: Tag of clan to create entries for.
        force: Insert new River Race clans regardless of time. Used for first time database setup.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    clan_id = cursor.fetchone()["id"]
    cursor.execute("SELECT MAX(id) AS id FROM seasons")
    season_id = cursor.fetchone()["id"]

    try:
        river_race_info = clash_utils.get_current_river_race_info(tag)
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

    if clash_utils.is_first_day_of_season() or force:
        for clan_tag, clan_name in river_race_info["clans"]:
            cursor.execute("INSERT INTO river_race_clans (clan_id, season_id, tag, name) VALUES (%s, %s, %s, %s)",
                            (clan_id, season_id, clan_tag, clan_name))

    database.commit()
    database.close()
