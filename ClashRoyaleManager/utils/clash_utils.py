"""Functions that return data from the Clash Royale API."""

import datetime
import re
import requests
from typing import Union

from config.credentials import CLASH_API_KEY
from utils.custom_types import ClanRole, ClashData
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
        req = requests.get(url="https://api.clashroyale.com/v1/cards",
                           headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

        if req.status_code == 200:
            get_total_cards.cached_total = len(req.json()["items"])
            get_total_cards.last_check_time = now

    return get_total_cards.cached_total


def get_clash_royale_user_data(tag: str) -> ClashData:
    """Get a user's relevant Clash Royale information.

    Args:
        tag: Valid player tag.

    Returns:
        A dictionary of relevant Clash Royale information.

    Raises:
        ResourceNotFound: Invalid tag was provided.
        GeneralAPIError: Something went wrong with the request.
    """
    req = requests.get(url=f"https://api.clashroyale.com/v1/players/%23{tag[1:]}",
                       headers={"Accept": "application/json", "authorization": f"Bearer {CLASH_API_KEY}"})

    if req.status_code != 200:
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

    return clash_data
