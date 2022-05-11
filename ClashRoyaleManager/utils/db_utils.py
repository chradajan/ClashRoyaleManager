"""Functions that interface with the database."""

from typing import Dict, List, Tuple, Union

import discord
import pymysql

import utils.discord_utils as discord_utils
from config.credentials import (
    IP,
    USERNAME,
    PASSWORD,
    DATABASE_NAME
)
from utils.custom_types import ClashData, SpecialRoles


def get_database_connection() -> Tuple[pymysql.Connection, pymysql.cursors.DictCursor]:
    """Establish connection to database.

    Returns:
        Database connection and cursor.
    """
    database = pymysql.connect(host=IP, user=USERNAME, password=PASSWORD, database=DATABASE_NAME, charset='utf8mb4')
    cursor = database.cursor(pymysql.cursors.DictCursor)
    return (database, cursor)


def get_guild_id() -> int:
    """Get saved Discord guild id.

    Returns:
        id of saved Discord guild.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT guild_id FROM variables")
    query_result = cursor.fetchone()
    database.close()
    return query_result["guild_id"]


def get_visitor_role_id() -> int:
    """Get id of Visitor role.

    Returns:
        id of Visitor role.
    """
    database, cursor = get_database_connection()
    cursor.execute("SELECT discord_role_id FROM special_discord_roles WHERE role = %s", (SpecialRoles.VISITOR.value))
    visitor_role_id = cursor.fetchone()["discord_role_id"]
    database.close()
    return visitor_role_id


def insert_clan(tag: str, name: str) -> int:
    """Insert a new clan into the clans table. Defaults to associating clan with the Visitor role.

    If the clan already exists, 

    Args:
        tag: Tag of clan to insert.
        name: Name of clan to insert.

    Returns:
        id of clan being inserted.
    """
    database, cursor = get_database_connection()
    cursor.execute("INSERT IGNORE INTO clans VALUES\
                    (DEFAULT, %s, %s, %s)", (tag, name, get_visitor_role_id()))
    cursor.execute("SELECT id FROM clans WHERE tag = %s", (tag))
    id = cursor.fetchone()["id"]
    database.commit()
    database.close()
    return id


def insert_new_user(clash_data: ClashData, member: discord.Member=None) -> bool:
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

    # Insert/update member
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

    # Create/update clan affiliation if user is in a clan
    if clash_data["clan_tag"] is not None:
        clash_data["clan_id"] = insert_clan(clash_data["clan_tag"], clash_data["clan_name"])
        clash_data["role_name"] = clash_data["role"].value

        cursor.execute("UPDATE clan_affiliations SET role = NULL WHERE user_id = %(user_id)s", clash_data)
        cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", clash_data)
        query_result = cursor.fetchone()

        if query_result is None:
            cursor.execute("INSERT INTO clan_affiliations VALUES (DEFAULT, %(user_id)s, %(clan_id)s, %(role_name)s, DEFAULT)",
                           clash_data)
            cursor.execute("SELECT id FROM clan_affiliations WHERE user_id = %(user_id)s AND clan_id = %(clan_id)s", clash_data)
            clash_data["clan_affiliation_id"] = cursor.fetchone()["id"]
        else:
            clash_data["clan_affiliation_id"] = query_result["id"]
            cursor.execute("UPDATE clan_affiliations SET role = %(role_name)s WHERE id = %(clan_affiliation_id)s", clash_data)

        # Create River Race entry if user is in a clan that tracks stats
        cursor.execute("SELECT track_stats FROM primary_clans WHERE clan_id = %(clan_id)s", clash_data)
        query_result = cursor.fetchone()

        if query_result is not None and query_result["track_stats"]:
            cursor.execute("SELECT id FROM river_races WHERE clan_id = %(clan_id)s AND season_id = (SELECT MAX(id) FROM seasons)",
                           clash_data)
            query_result = cursor.fetchone()

            if query_result is not None:
                clash_data["river_race_id"] = query_result["id"]
                cursor.execute("INSERT IGNORE INTO river_race_user_data (clan_affiliation_id, river_race_id, last_check) VALUES\
                                (%(clan_affiliation_id)s, %(river_race_id)s, (SELECT last_check FROM variables))",
                               clash_data)

    database.commit()
    database.close()
    return True


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
