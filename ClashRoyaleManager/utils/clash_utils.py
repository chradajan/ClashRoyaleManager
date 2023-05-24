"""Functions that return data from the Clash Royale API."""

import datetime
import re
import requests
from typing import Dict, List, Tuple, Union

import utils.db_utils as db_utils
from config.credentials import CLASH_API_KEY
from log.logger import LOG, log_message
from utils.custom_types import (
    Battles,
    BattleStats,
    BoatBattle,
    Card,
    ClanRole,
    ClashData,
    DecksReport,
    Duel,
    Participant,
    PvPBattle,
    PvPBattleResult,
    RiverRaceClan,
    RiverRaceInfo,
    RiverRaceStatus
)
from utils.exceptions import GeneralAPIError, ResourceNotFound

MAX_CARD_LEVEL = 14

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


def royale_api_url(tag: str) -> str:
    """Get a link to a user's RoyaleAPI page.

    Args:
        tag: Tag of user to get link to.

    Returns:
        URL of RoyaleAPI page.
    """
    return f"https://royaleapi.com/player/{tag[1:]}"


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


def is_first_day_of_season() -> bool:
    """Check if it's the first Monday of the current month, indicating that today is the start of a new season.

    Precondition:
        Should only be called on a Monday.

    Returns:
        Whether it's the beginning of a new season.
    """
    current_time = datetime.datetime.utcnow()
    return current_time.month != (current_time - datetime.timedelta(days=7)).month


def is_colosseum_week() -> bool:
    """Check if it's currently a Colosseum week.

    Note:
        This does not work on Mondays between midnight and the daily reset time.

    Returns:
        Whether it's a Colosseum week.
    """
    now = datetime.datetime.utcnow()
    monday = now - datetime.timedelta(days=now.weekday())
    return monday.month != (monday + datetime.timedelta(days=7)).month


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


def get_all_cards() -> List[Card]:
    """Get a list of all cards currently in the game.

    Returns:
        A list of all cards.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    LOG.info("Getting a list of all cards available in the game.")
    req = requests.get(url="https://api.clashroyale.com/v1/cards",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        raise GeneralAPIError

    json_obj = req.json()
    cards_list = []

    for card in json_obj["items"]:
        cards_list.append(
            {
                "name": card["name"],
                "id": card["id"],
                "level": card["maxLevel"],
                "max_level": card["maxLevel"],
                "url": card["iconUrls"].get("medium")
            }
        )

    return cards_list


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
        card_level = MAX_CARD_LEVEL - (card["maxLevel"] - card["level"])
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
        "colosseum_week": is_colosseum_week(),
        "completed_saturday": (race_info["periodIndex"] % 7 == 6
                               and race_info["clan"]["fame"] >= 10000
                               and race_info["periodType"].lower() != "colosseum"),
        "week": (race_info["periodIndex"] // 7) + 1,
        "clans": [(clan["tag"], clan["name"]) for clan in race_info["clans"]]
    }
    return river_race_info


def get_clans_in_race(tag: str, post_race: bool) -> Dict[str, RiverRaceClan]:
    """Get a dictionary of stats for each clan in a River Race.

    Args:
        tag: Get the clans in this clan's River Race.
        post_race: Whether to get info of current River Race or most recent one.

    Returns:
        Dictionary mapping each clan's tag to its stats.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(log_message("Getting River Race clans info", tag=tag, post_race=post_race))

    if post_race:
        req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/riverracelog?limit=1",
                           headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code != 200:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
            if req.status_code == 404:
                raise ResourceNotFound
            else:
                raise GeneralAPIError

        json_obj = req.json()
        clans = [clan["clan"] for clan in json_obj["items"][0]["standings"]]
    else:
        req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/currentriverrace",
                           headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code != 200:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
            if req.status_code == 404:
                raise ResourceNotFound
            else:
                raise GeneralAPIError

        json_obj = req.json()
        clans = json_obj["clans"]

    clans_dict = {}

    for clan in clans:
        medals = 0
        decks_used_total = 0
        decks_used_today = 0

        for participant in clan["participants"]:
            medals += participant["fame"]
            decks_used_total += participant["decksUsed"]
            decks_used_today += participant["decksUsedToday"]

        clans_dict[clan["tag"]] = {
            "tag": clan["tag"],
            "name": clan["name"],
            "medals": medals,
            "total_decks_used": decks_used_total,
            "decks_used_today": decks_used_today,
            "completed": clan["fame"] >= 10000
        }

    return clans_dict


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


def get_river_race_participants(tag: str, force: bool=False) -> List[Participant]:
    """Get a list of participants in a clan's current River Race.

    Args:
        tag: Clan to get participants of.
        force: If true, ignore any cached data and get latest data from API.

    Returns:
        List of participants in the specified clan.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    if not hasattr(get_river_race_participants, "cached_data"):
        get_river_race_participants.cached_data = {}
        get_river_race_participants.last_checks = {}
        primary_clans = db_utils.get_primary_clans()

        for clan in primary_clans:
            get_river_race_participants.cached_data[clan["tag"]] = None
            get_river_race_participants.last_checks[clan["tag"]] = None

    now = datetime.datetime.utcnow()

    if (get_river_race_participants.last_checks.get(tag) is None
            or (now - get_river_race_participants.last_checks[tag]).seconds > 60
            or force):
        LOG.info(f"Getting river race participants in clan {tag}")
        req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/currentriverrace",
                        headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code != 200:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
            if req.status_code == 404:
                raise ResourceNotFound
            else:
                raise GeneralAPIError

        json_obj = req.json()
        participants = []

        for participant in json_obj["clan"]["participants"]:
            participant["tag"] = participant.pop("tag")
            participant["name"] = participant.pop("name")
            participant["medals"] = participant.pop("fame")
            participant["repair_points"] = participant.pop("repairPoints")
            participant["boat_attacks"] = participant.pop("boatAttacks")
            participant["decks_used"] = participant.pop("decksUsed")
            participant["decks_used_today"] = participant.pop("decksUsedToday")
            participants.append(participant)

        if tag in get_river_race_participants.cached_data:
            get_river_race_participants.cached_data[tag] = participants
            get_river_race_participants.last_checks[tag] = now

        return participants

    LOG.info(f"Getting cached River Race participants in clan {tag}")
    return get_river_race_participants.cached_data[tag]


def get_prior_river_race_participants(tag: str, force: bool=True) -> List[Participant]:
    """Get participants in most recently completed River Race.

    Args:
        tag: Tag of clan to get participants of.
        force: If true, ignore any cached data and get latest data from API.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    if not hasattr(get_prior_river_race_participants, "cached_data"):
        get_prior_river_race_participants.cached_data = {}
        get_prior_river_race_participants.last_checks = {}
        primary_clans = db_utils.get_primary_clans()

        for clan in primary_clans:
            get_prior_river_race_participants.cached_data[clan["tag"]] = None
            get_prior_river_race_participants.last_checks[clan["tag"]] = None

    now = datetime.datetime.utcnow()

    if (get_prior_river_race_participants.last_checks.get(tag) is None
            or (now - get_prior_river_race_participants.last_checks[tag]).seconds > 60
            or force):
        LOG.info(f"Getting participants from most recent river race of clan {tag}")
        req = requests.get(url=f"https://api.clashroyale.com/v1/clans/%23{tag[1:]}/riverracelog?limit=1",
                        headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code != 200:
            LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
            if req.status_code == 404:
                raise ResourceNotFound
            else:
                raise GeneralAPIError

        json_obj = req.json()
        participants = []
        index = 0

        for clan in json_obj["items"][0]["standings"]:
            if clan["clan"]["tag"] == tag:
                break

            index += 1

        for participant in json_obj["items"][0]["standings"][index]["clan"]["participants"]:
            participant["tag"] = participant.pop("tag")
            participant["name"] = participant.pop("name")
            participant["medals"] = participant.pop("fame")
            participant["repair_points"] = participant.pop("repairPoints")
            participant["boat_attacks"] = participant.pop("boatAttacks")
            participant["decks_used"] = participant.pop("decksUsed")
            participant["decks_used_today"] = participant.pop("decksUsedToday")
            participants.append(participant)

        if tag in get_prior_river_race_participants.cached_data:
            get_prior_river_race_participants.cached_data[tag] = participants
            get_prior_river_race_participants.last_checks[tag] = now

        return participants

    LOG.info(f"Getting cached prior River Race participants of clan {tag}")
    return get_prior_river_race_participants.cached_data[tag]


def get_deck_usage_today(tag: str) -> Dict[str, int]:
    """Get a dictionary of users in a clan and how many decks they've used today.

    Args:
        tag: Tag of clan to get deck usage in.

    Returns:
        Dictionary mapping player tags to deck usage today.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting dictionary of users and how many decks they've used in clan {tag}")
    participants = get_river_race_participants(tag, True)
    active_members = get_active_members_in_clan(tag, True).copy()
    deck_usage = {}

    for participant in participants:
        deck_usage[participant["tag"]] = participant["decks_used_today"]
        active_members.pop(participant["tag"], None)

    for tag in active_members:
        deck_usage[tag] = 0

    return deck_usage


def get_decks_report(tag: str) -> DecksReport:
    """Get a report containing detailed information about deck usage today.
    Args:
        tag: Tag of clan to get decks report of.

    Returns:
        Detailed lists of specified clan's deck usage.
            remaining_decks: Maximum number of decks that could still be used today.
            participants: Number of players who have used at least 1 deck today.
            active_members_with_no_decks_used: Number of players in the clan that have not used decks.
            active_members_with_remaining_decks: List of members in clan that could still battle.
            active_members_without_remaining_decks: List of members in clan that have used 4 decks today.
            inactive_members_with_decks_used: List of members no longer in clan that battled today while in the clan.
            locked_out_active_members: List of members in clan that are locked out of battling today.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting decks report for {tag}")
    active_members = get_active_members_in_clan(tag)
    participants = get_river_race_participants(tag)

    decks_report: DecksReport = {
        "remaining_decks": 200,
        "participants": 0,
        "active_members_with_no_decks_used": 0,
        "active_members_with_remaining_decks": [],
        "active_members_without_remaining_decks": [],
        "inactive_members_with_decks_used": [],
        "locked_out_active_members": []
    }

    for participant in participants:
        if participant["decks_used_today"] > 0:
            decks_report["remaining_decks"] -= participant["decks_used_today"]
            decks_report["participants"] += 1

    for participant in participants:
        tag = participant["tag"]

        if tag in active_members:
            name = active_members[tag]["name"]
        else:
            name = participant["name"]

        if participant["tag"] in active_members:
            if participant["decks_used_today"] == 4:
                decks_report["active_members_without_remaining_decks"].append((tag, name, 0))
            elif participant["decks_used_today"] == 0:
                decks_report["active_members_with_no_decks_used"] += 1
                if decks_report["participants"] == 50:
                    decks_report["locked_out_active_members"].append((tag, name, 4))
                else:
                    decks_report["active_members_with_remaining_decks"].append((tag, name, 4))
            else:
                decks_report["active_members_with_remaining_decks"].append((tag, name, (4 - participant["decks_used_today"])))
        elif participant["decks_used_today"] > 0:
            decks_report["inactive_members_with_decks_used"].append((tag, name, (4 - participant["decks_used_today"])))

    decks_report["active_members_with_remaining_decks"].sort(key=lambda x: (x[2], x[1].lower()))
    decks_report["active_members_without_remaining_decks"].sort(key=lambda x: (x[2], x[1].lower()))
    decks_report["inactive_members_with_decks_used"].sort(key=lambda x: (x[2], x[1].lower()))
    decks_report["locked_out_active_members"].sort(key=lambda x: (x[2], x[1].lower()))
    return decks_report


def get_remaining_decks_today(tag: str) -> Dict[str, int]:
    """Get a dictionary of users that have remaining decks available.

    Args:
        tag: Tag of clan to get remaining decks for.

    Returns:
        Dictionary mapping player tags to their remaining decks count if they have not used four decks.
    """
    LOG.info(f"Getting dictionary of users and how many decks they have remaining in clan {tag}")


def interpret_regular_battle(raw_battle: dict) -> PvPBattle:
    """Interpret a regular PvP battle and convert into a PvPBattle dictionary.

    Args:
        raw_battle: Dictionary of json data from Clash API representing a regular PvP battle.

    Returns:
        A PvPBattle representation of raw_battle.
    """
    def interpret_results(raw_result: dict) -> PvPBattleResult:
        analyzed_result: PvPBattleResult = {
            "crowns": raw_result["crowns"],
            "elixir_leaked": raw_result["elixirLeaked"],
            "kt_hit_points": raw_result.get("kingTowerHitPoints", 0),
            "pt1_hit_points": 0,
            "pt2_hit_points": 0,
            "deck": []
        }

        if ("princessTowersHitPoints" in raw_result) and (raw_result["princessTowersHitPoints"] is not None):
            if len(raw_result["princessTowersHitPoints"]) == 1:
                analyzed_result["pt1_hit_points"] = raw_result["princessTowersHitPoints"][0]
                analyzed_result["pt2_hit_points"] = 0
            else:
                analyzed_result["pt1_hit_points"] = raw_result["princessTowersHitPoints"][0]
                analyzed_result["pt2_hit_points"] = raw_result["princessTowersHitPoints"][1]
        else:
            analyzed_result["pt1_hit_points"] = 0
            analyzed_result["pt2_hit_points"] = 0

        for card in raw_result["cards"]:
            analyzed_result["deck"].append(
                {
                    "name": card["name"],
                    "id": card["id"],
                    "level": card["level"],
                    "max_level": card["maxLevel"],
                    "url": card["iconUrls"].get("medium")
                }
            )

        return analyzed_result


    pvp_battle: PvPBattle = {
        "time": battletime_to_datetime(raw_battle["battleTime"]),
        "won": False,
        "game_type": raw_battle["gameMode"]["name"],
        "team_results": interpret_results(raw_battle["team"][0]),
        "opponent_results": interpret_results(raw_battle["opponent"][0])
    }

    if pvp_battle["team_results"]["crowns"] > pvp_battle["opponent_results"]["crowns"]:
        pvp_battle["won"] = True

    return pvp_battle


def interpret_duel(raw_duel: dict) -> Duel:
    """Interpret a duel and convert into a Duel dictionary.

    Args:
        raw_duel: Dictionary of json data from Clash API representing a duel.

    Returns:
        A Duel representation of raw_duel.
    """
    def interpret_results(raw_round: dict) -> PvPBattleResult:
        analyzed_result: PvPBattleResult = {
            "crowns": raw_round["crowns"],
            "elixir_leaked": raw_round["elixirLeaked"],
            "kt_hit_points": raw_round.get("kingTowerHitPoints", 0),
            "pt1_hit_points": 0,
            "pt2_hit_points": 0,
            "deck": []
        }

        if ("princessTowersHitPoints" in raw_round) and (raw_round["princessTowersHitPoints"] is not None):
            if len(raw_round["princessTowersHitPoints"]) == 1:
                analyzed_result["pt1_hit_points"] = raw_round["princessTowersHitPoints"][0]
                analyzed_result["pt2_hit_points"] = 0
            else:
                analyzed_result["pt1_hit_points"] = raw_round["princessTowersHitPoints"][0]
                analyzed_result["pt2_hit_points"] = raw_round["princessTowersHitPoints"][1]
        else:
            analyzed_result["pt1_hit_points"] = 0
            analyzed_result["pt2_hit_points"] = 0

        for card in raw_round["cards"]:
            analyzed_result["deck"].append(
                {
                    "name": card["name"],
                    "id": card["id"],
                    "level": card["level"],
                    "max_level": card["maxLevel"],
                    "url": card["iconUrls"].get("medium")
                }
            )

        return analyzed_result

    duel: Duel = {
        "time": battletime_to_datetime(raw_duel["battleTime"]),
        "won": False,
        "battle_wins": 0,
        "battle_losses": 0,
        "battles": []
    }

    game_type = raw_duel["gameMode"]["name"]

    for i, raw_round in enumerate(raw_duel["team"][0]["rounds"]):
        pvp_battle: PvPBattle = {
            "time": battletime_to_datetime(raw_duel["battleTime"]),
            "won": False,
            "game_type": game_type,
            "team_results": interpret_results(raw_round),
            "opponent_results": interpret_results(raw_duel["opponent"][0]["rounds"][i])
        }

        if pvp_battle["team_results"]["crowns"] > pvp_battle["opponent_results"]["crowns"]:
            pvp_battle["won"] = True
            duel["battle_wins"] += 1
        else:
            duel["battle_losses"] += 1

        duel["battles"].append(pvp_battle)

    if duel["battle_wins"] > duel["battle_losses"]:
        duel["won"] = True

    return duel


def interpret_boat_battle(raw_battle: dict) -> BoatBattle:
    """Interpret a boat battle and convert into a BoatBattle dictionary.

    Args:
        raw_battle: Dictionary of json data from Clash API representing a boat battle.

    Returns:
        A BoatBattle representation of raw_battle.
    """
    boat_battle: BoatBattle = {
        "time": battletime_to_datetime(raw_battle["battleTime"]),
        "won": raw_battle["boatBattleWon"],
        "elixir_leaked": raw_battle["team"][0]["elixirLeaked"],
        "new_towers_destroyed": raw_battle["newTowersDestroyed"],
        "prev_towers_destroyed": raw_battle["prevTowersDestroyed"],
        "remaining_towers": raw_battle["remainingTowers"],
        "deck": []
    }

    for card in raw_battle["team"][0]["cards"]:
        boat_battle["deck"].append(
            {
                "name": card["name"],
                "id": card["id"],
                "level": card["level"],
                "max_level": card["maxLevel"],
                "url": card["iconUrls"].get("medium")
            }
        )

    return boat_battle


def get_battle_day_stats(player_tag: str,
                         clan_tag: str,
                         last_check: datetime.datetime,
                         current_time: datetime.datetime) -> Tuple[BattleStats, Battles]:
    """Get wins/losses of each River Race game mode for a user.

    Args:
        player_tag: Tag of user to get battlelog of.
        clan_tag: Only consider matches played while in this clan.
        last_check: Only consider matches played on or after this time.
        current_time: Only consider matches played before this time.

    Returns:
        Tuple of the user's stats and their battles.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(log_message("Getting battle log of user", player_tag=player_tag, clan_tag=clan_tag, last_check=last_check))
    req = requests.get(url=f"https://api.clashroyale.com/v1/players/%23{player_tag[1:]}/battlelog",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    battle_log = req.json()
    battles_to_analyze = []
    last_check = last_check.replace(tzinfo=datetime.timezone.utc)
    current_time = current_time.replace(tzinfo=datetime.timezone.utc)

    for battle in battle_log:
        battle_time = battletime_to_datetime(battle["battleTime"])

        if ((battle["type"].startswith("riverRace") or battle["type"] == "boatBattle")
                and last_check <= battle_time < current_time
                and battle["team"][0]["clan"]["tag"] == clan_tag):
            battles_to_analyze.append(battle)

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

    battles: Battles = {
        "pvp_battles": [],
        "duels": [],
        "boat_battles": []
    }

    for raw_battle in battles_to_analyze:
        if raw_battle["type"] == "riverRacePvP":
            pvp_battle = interpret_regular_battle(raw_battle)
            battles["pvp_battles"].append(pvp_battle)

            if pvp_battle["game_type"] == "CW_Battle_1v1":
                if pvp_battle["won"]:
                    stats["regular_wins"] += 1
                else:
                    stats["regular_losses"] += 1
            else:
                if pvp_battle["won"]:
                    stats["special_wins"] += 1
                else:
                    stats["special_losses"] += 1
        elif (raw_battle["type"] == "boatBattle") and (raw_battle["boatBattleSide"] == "attacker"):
            boat_battle = interpret_boat_battle(raw_battle)
            battles["boat_battles"].append(boat_battle)

            if boat_battle["won"]:
                stats["boat_wins"] += 1
            else:
                stats["boat_losses"] += 1
        elif raw_battle["type"].startswith("riverRaceDuel"):
            duel = interpret_duel(raw_battle)
            battles["duels"].append(duel) 
            stats["duel_wins"] += duel["battle_wins"]
            stats["duel_losses"] += duel["battle_losses"]

            if duel["won"]:
                stats["series_wins"] += 1
            else:
                stats["series_losses"] += 1

    return (stats, battles)


def battled_for_other_clan(player_tag: str, clan_tag: str, time: datetime.datetime) -> bool:
    """Check if a user has already used war decks today for a different clan.

    Args:
        player_tag: Tag of user to check battle log of.
        clan_tag: Current clan of user.
        time: Check for decks used after this time.

    Returns:
        Whether the specified user battled for a different clan today.
    """
    LOG.info(log_message("Checking for previous war participation", player_tag=player_tag, clan_tag=clan_tag, time=time))

    req = requests.get(url=f"https://api.clashroyale.com/v1/players/%23{player_tag[1:]}/battlelog",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
        LOG.warning(log_message(msg="Bad request", status_code=req.status_code))
        if req.status_code == 404:
            raise ResourceNotFound
        else:
            raise GeneralAPIError

    time = time.replace(tzinfo=datetime.timezone.utc)
    battle_log = req.json()

    for battle in battle_log:
        battle_time = battletime_to_datetime(battle["battleTime"])

        if ((battle["type"].startswith("riverRace") or battle["type"] == "boatBattle")
                and time < battle_time
                and battle["team"][0]["clan"]["tag"] != clan_tag):
            return True

    return False


def medals_report(tag: str, threshold: int) -> List[Tuple[str, int]]:
    """Get a list of users in a clan below the specified medals threshold.

    Args:
        tag: Tag of clan to get report for.
        threshold: Get a list of members in the clan with fewer medals than this.

    Returns:
        List of users's names and medals below the threshold, ordered from lowest to highest.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(log_message("Getting medals report", tag=tag, threshold=threshold))
    active_members = get_active_members_in_clan(tag)
    members = []

    if db_utils.is_battle_time(tag):
        participants = get_river_race_participants(tag)
    else:
        participants = get_prior_river_race_participants(tag)

    for participant in participants:
        if participant["medals"] < threshold and participant["tag"] in active_members:
            members.append((active_members[participant["tag"]]["name"], participant["medals"]))

    members.sort(key=lambda x: (x[1], x[0].lower()))
    return members


def river_race_status(tag: str) -> List[RiverRaceStatus]:
    """Get number of decks still available today to each clan in a River Race.

    Args:
        tag: Tag of clan to check River Race status of.

    Returns:
        List of statuses order from lowest total remaining decks to highest.

    Raises:
        GeneralAPIError: Something went wrong with the request.
        ResourceNotFound: Invalid tag was provided.
    """
    LOG.info(f"Getting River Race status for {tag}")
    race_info = get_current_river_race_info(tag)
    river_race_status: List[RiverRaceStatus] = []

    for clan_tag, name in race_info["clans"]:
        decks_report = get_decks_report(clan_tag)
        total_remaining_decks = decks_report["remaining_decks"]
        active_remaining_decks = 0

        for _, _, decks_remaining in decks_report["active_members_with_remaining_decks"]:
            active_remaining_decks += decks_remaining

        active_remaining_decks = min(active_remaining_decks, total_remaining_decks)

        river_race_status.append(
            {
                "tag": clan_tag,
                "name": name,
                "total_remaining_decks": total_remaining_decks,
                "active_remaining_decks": active_remaining_decks
            }
        )

    river_race_status.sort(key=lambda x: (x["total_remaining_decks"], x["active_remaining_decks"]))
    return river_race_status
