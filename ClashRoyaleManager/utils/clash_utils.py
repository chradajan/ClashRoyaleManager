"""Functions that return data from the Clash Royale API."""

import datetime
import re
import requests
from typing import Dict, Union

import utils.db_utils as db_utils
from config.credentials import CLASH_API_KEY
from log.logger import LOG, log_message
from utils.custom_types import ClanRole, ClashData, RiverRaceInfo
from utils.exceptions import GeneralAPIError, ResourceNotFound

def process_clash_royale_tag(input: str) -> Union[str, None]:
    """Take a user's input and validate that it's a valid Supercell tag.
    
    Valid tags will only contain the letters CGJLPQRUVY and the numbers 0289. They're length depends on when the tag was created,
    will most likely be <= 9 characters.

    Args:
        input: User inputted Supercell tag.

    Returns:
        A properly formatted Supercell tag if the input is valid, otherwise None.
    """
    processed_tag = None
    input = input.upper().strip()
    input = input.replace('O', '0')

    if input.startswith('#'):
        input = input[1:]

    if len(input) < 12:
        matched_tag = re.fullmatch(r"[CGJLPQRUVY0289]+", input)

        if matched_tag:
            processed_tag = '#' + matched_tag.group(0)

    return processed_tag


def battletime_to_datetime(battle_time: str) -> datetime.datetime:
    """Convert a time string provided by the API into a datetime object.

    Args:
        battle_time: API time string in the form of "yyyymmddThhmmss.000Z"

    Returns:
        Datetime object of API time string.
    """
    year = int(battle_time[:4])
    month = int(battle_time[4:6])
    day = int(battle_time[6:8])
    hour = int(battle_time[9:11])
    minute = int(battle_time[11:13])
    second = int(battle_time[13:15])
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)


def get_total_cards() -> int:
    """Get total number of cards available in the game.

    Return a cached value. Cached value is updated when this function is called after 24 hours have passed since the last time the
    total number of cards was calculated.

    Returns:
        Total number of cards in the game.
    """
    if not hasattr(get_total_cards, "cached_total"):
        get_total_cards.cached_total = 0
        get_total_cards.last_check_time = None

    now = datetime.datetime.utcnow()

    if get_total_cards.last_check_time is None or (now - get_total_cards.last_check_time).days > 0:
        LOG.info("Getting total cards available in game")
        req = requests.get(url="https://api.clashroyale.com/v1/cards",
                           headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code == 200:
            get_total_cards.cached_total = len(req.json()["items"])
            get_total_cards.last_check_time = now
        else:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
    else:
        LOG.info("Getting cached total cards available in game")

    return get_total_cards.cached_total


def get_clash_royale_user_data(tag: str) -> ClashData:
    """Get a user's relevant Clash Royale information.

    Args:
        tag: Valid player tag.

    Returns:
        A dictionary of relevant Clash Royale information.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting Clash Royale data of user {tag}")
    req = requests.get(url=f"https://api.clashroyale.com/v1/players/%23{tag[1:]}",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    json_obj = req.json()
    user_in_clan = 'clan' in json_obj

    clash_data: ClashData = {
        "tag": json_obj["tag"],
        "name": json_obj["name"],
        "role": ClanRole(json_obj["role"].lower()) if "role" in json_obj else None,
        "exp_level": json_obj["expLevel"],
        "trophies": json_obj["trophies"],
        "best_trophies": json_obj["bestTrophies"],
        "cards": {i: 0 for i in range(1, 15)},
        "found_cards": 0,
        "total_cards": get_total_cards(),
        "clan_name": json_obj["clan"]["name"] if user_in_clan else None,
        "clan_tag": json_obj["clan"]["tag"] if user_in_clan else None
    }

    for card in json_obj["cards"]:
        card_level = 14 - (card["maxLevel"] - card["level"])
        clash_data["cards"][card_level] += 1
        clash_data["found_cards"] += 1

    LOG.info(log_message("User data: ", clash_data=clash_data))
    return clash_data


def get_clan_name(tag: str) -> str:
    """Get name of clan from its tag.

    Args:
        tag: Tag of clan to get name of.

    Returns:
        Name of clan.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting name of clan {tag}")
    req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    json_obj = req.json()
    return json_obj["name"]


def get_current_river_race_info(tag: str) -> RiverRaceInfo:
    """Get information about the current River Race of the specified clan.

    Args:
        tag: Tag of clan to get River Race data of.

    Returns:
        River Race data of specified clan.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting current river race info for clan {tag}")
    req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/currentriverrace",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    race_info = req.json()

    req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/riverracelog?limit=1",
                           headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    last_race = req.json()
    last_race_end_time = battletime_to_datetime(last_race["items"][0]["createdDate"])

    river_race_info: RiverRaceInfo = {
        "tag": race_info["clan"]["tag"],
        "name": race_info["clan"]["name"],
        "start_time": last_race_end_time,
        "colosseum_week": race_info["periodType"].lower() == "colosseum",
        "completed_saturday": (race_info["periodIndex"] % 7 == 6
                                and race_info["clan"]["fame"] >= 10000
                                and race_info["periodType"].lower() != "colosseum"),
        "week": (race_info["periodIndex"] // 7) + 1,
        "clans": [(clan["tag"], clan["name"]) for clan in race_info["clans"]]
    }
    return river_race_info


def get_active_members_in_clan(tag: str, force: bool=False) -> Dict[str, ClashData]:
    """Get a dictionary of active members in a clan.

    Args:
        tag: Tag of clan to get members of.
        force: If true, ignore any cached data and get latest data from API.

    Returns:
        Dictionary of active members in the specified clan. best_trophies, cards, found_cards, total_cards, and clan_name fields are
        all populated but do not contain actual data.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    if not hasattr(get_active_members_in_clan, "cached_data"):
        get_active_members_in_clan.cached_data = {}
        get_active_members_in_clan.last_checks = {}
        primary_clans = db_utils.get_primary_clans()

        for clan in primary_clans:
            get_active_members_in_clan.cached_data[clan["tag"]] = None
            get_active_members_in_clan.last_checks[clan["tag"]] = None

    now = datetime.datetime.utcnow()

    if (get_active_members_in_clan.last_checks.get(tag) is None 
            or (now - get_active_members_in_clan.last_checks[tag]).seconds > 60
            or force):
        LOG.info(f"Getting active members of clan {tag}")
        req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/members",
                            headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code != 200:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
            if req.status_code == 404:
                raise ResourceNotFound
            else:
                raise GeneralAPIError

        json_obj = req.json()
        active_members = {}

        for member in json_obj["items"]:
            active_members[member["tag"]] = {
                "tag": member["tag"],
                "name": member["name"],
                "role": ClanRole(member["role"].lower()),
                "exp_level": member["expLevel"],
                "trophies": member["trophies"],
                "best_trophies": -1,
                "cards": {},
                "found_cards": -1,
                "total_cards": -1,
                "clan_name": "",
                "clan_tag": tag
            }

        if tag in get_active_members_in_clan.cached_data:
            get_active_members_in_clan.cached_data[tag] = active_members
            get_active_members_in_clan.last_checks[tag] = now

        return active_members

    LOG.info(f"Getting cached active members of clan {tag}")
    return get_active_members_in_clan.cached_data[tag]
