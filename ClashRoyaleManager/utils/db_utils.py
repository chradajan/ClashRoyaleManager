"""Functions that interface with the database."""

from optparse import Option
from typing import Dict, List, Optional, Tuple, Union

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
from log.logger import LOG
from utils.custom_types import (
    ClanRole,
    ClashData,
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


def insert_clan(tag: str, name: str) -> int:
    """Insert a new clan into the clans table. Update its name if it already exists.

    Args:
        tag: Tag of clan to insert.
        name: Name of clan to insert.

    Returns:
        ID of clan being inserted.
    """
    database, cursor = get_database_connection()
    cursor.execute("INSERT INTO clans (tag, name, discord_role_id) VALUES (%s, %s, %s)\
                    ON DUPLICATE KEY UPDATE name = %s",
                   (tag, name, get_special_role_id(SpecialRole.Visitor), name))
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    id = cursor.fetchone()["id"]
    database.commit()
    database.close()
    return id


def update_clan_affiliation(clash_data: ClashData):
    """Nullify role of any existing clan affiliations for the given user. Update/create a clan affiliation for their current clan.

    Args:
        clash_data: Data of user to update clan_affiliations for.

    Precondition:
        clash_data must contain a key called 'user_id' corresponding to their key in the users table.
    """
    database, cursor = get_database_connection()
    # Nullify any existing affiliations.
    cursor.execute("UPDATE clan_affiliations SET role = NULL WHERE user_id = %(user_id)s", clash_data)

    if clash_data["clan_tag"] is not None:
        # Create/update clan affiliation for user if they are in a clan.
        clash_data["clan_id"] = insert_clan(clash_data["clan_tag"], clash_data["clan_name"])
        clash_data["role_name"] = clash_data["role"].value
        cursor.execute("INSERT INTO clan_affiliations (user_id, clan_id, role) VALUES (%(user_id)s, %(clan_id)s, %(role_name)s)\
                        ON DUPLICATE KEY UPDATE role = %(role_name)s",
                       clash_data)

        # Check if user is in a primary clan that also tracks stats.
        cursor.execute("SELECT track_stats FROM primary_clans WHERE clan_id = %(clan_id)s", clash_data)
        query_result = cursor.fetchone()

        if query_result is not None and query_result["track_stats"]:
            # Create River Race user data entry for user if necessary.
            cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", clash_data)
            clash_data["clan_affiliation_id"] = cursor.fetchone()["id"]

            cursor.execute("SELECT id FROM river_races WHERE clan_id = %(clan_id)s AND season_id = (SELECT MAX(id) FROM seasons)",
                           clash_data)
            query_result = cursor.fetchone()

            if query_result is not None:
                clash_data["river_race_id"] = query_result["id"]
                cursor.execute("INSERT INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check) VALUES\
                                (%(clan_affiliation_id)s, %(river_race_id)s, (SELECT last_check FROM variables))\
                                ON DUPLICATE KEY UPDATE clan_affiliation_id = clan_affiliation_id",
                                clash_data)

    database.commit()
    database.close()


def insert_new_user(clash_data: ClashData, member: Optional[discord.Member]=None) -> bool:
    """
    Insert a new user into the database.

    Args:
        clash_data: Clash Royale data of user to be inserted.
        member: Member object of user to be inserted if they join through the Discord server. If not provided, discord_name and
                discord_id will be left NULL.

    Returns:
        True if member was inserted, False if player tag is already associated with a user on the Discord server.
    """
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
        cursor.execute("SELECT id FROM users WHERE discord_id = %(discord_id)s", clash_data)
        clash_data["user_id"] = cursor.fetchone()["id"]
    else:
        clash_data["user_id"] = query_result["id"]

        if query_result["discord_id"] is None:
            cursor.execute("UPDATE users SET discord_id = %(discord_id)s, discord_name = %(discord_name)s, name = %(name)s\
                            WHERE id = %(user_id)s",
                           clash_data)
        else:
            database.close()
            return False

    database.commit()
    database.close()
    update_clan_affiliation(clash_data)
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


def get_clans_in_database() -> Dict[str, str]:
    """Get all clans saved in the database.

    Returns:
        Dictionary mapping clan tags to names.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT tag, name FROM clans")
    query_result = cursor.fetchall()
    tags = {clan["tag"]: clan["name"] for clan in query_result}
    database.close()
    return tags


def get_user_in_database(search_key: Union[int, str]) -> List[Tuple[str, str, str]]:
    """Find a user(s) in the database corresponding to the search key.

    First try searching for a user where discord_id == search_key if key is an int, otherwise where player_tag == search_key. If no
    results are found, then try searching where player_name == search_key. Player names are not unique and could result in finding
    multiple users. If this occurs, all users that were found are returned.

    Args:
        Key to search for in database. Can be discord id, player tag, or player name.

    Returns:
        List of tuples of (name, tag, clan_name).
    """
    database, cursor = get_database_connection()

    if isinstance(search_key, int):
        cursor.execute("SELECT users.name AS player_name, users.tag AS player_tag, clans.name AS clan_name FROM users\
                        INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                        INNER JOIN clans ON clan_affiliations.clan_id = clans.id\
                        WHERE users.discord_id = %s",
                       (search_key))
        query_result = cursor.fetchall()
    else:
        cursor.execute("SELECT users.name AS player_name, users.tag AS player_tag, clans.name AS clan_name FROM users\
                        INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                        INNER JOIN clans ON clan_affiliations.clan_id = clans.id\
                        WHERE users.tag = %s",
                       (search_key))
        query_result = cursor.fetchall()

        if not query_result:
            cursor.execute("SELECT users.name AS player_name, users.tag AS player_tag, clans.name AS clan_name FROM users\
                            INNER JOIN clan_affiliations ON users.id = clan_affiliations.user_id\
                            INNER JOIN clans ON clan_affiliations.clan_id = clans.id\
                            WHERE users.name = %s",
                           (search_key))
            query_result = cursor.fetchall()

    database.close()
    results = [(user["player_name"], user["player_tag"], user["clan_name"]) for user in query_result]
    return results


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


def get_primary_clans() -> List[PrimaryClan]:
    """Get all primary clans.

    Returns:
        List of primary clans.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT * FROM primary_clans INNER JOIN clans ON primary_clans.clan_id = clans.id")
    query_result = cursor.fetchall()
    database.close()
    primary_clans: List[PrimaryClan] = []

    for clan in query_result:
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
    query_result = cursor.fetchall()

    for user in query_result:
        clan_affiliations.append((user["player_tag"], user["name"], user["clan_tag"], ClanRole(user["role"])))

    cursor.execute("SELECT tag, name FROM users WHERE id NOT IN (SELECT user_id FROM clan_affiliations)")
    query_result = cursor.fetchall()

    for user in query_result:
        clan_affiliations.append((user["tag"], user["name"], None, None))

    database.close()
    return clan_affiliations


def clean_up_database():
    """Update the database to reflect changes to members in the primary clans.

    Updates any user that is either
        a. In a primary clan but is not affiliated with that clan
        b. In a primary clan but is not affiliated with the correct role
        c. In a primary clan but has changed their in-game username
        d. Not in a primary clan but is currently affiliated with one

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
