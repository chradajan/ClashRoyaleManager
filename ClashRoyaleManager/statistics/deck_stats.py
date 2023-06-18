"""Functions related to getting deck information from database."""

from collections import defaultdict
from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Dict, FrozenSet, List, Set, Tuple, TypedDict


@dataclass
class Deck:
    """Class for recording a deck, its win/loss stats, and users."""
    deck: FrozenSet[int]
    win_rate: float
    matches_played: int
    avg_elixir: float
    cycle_cost: int
    users: FrozenSet[str]


class Rarity(Enum):
    """Enum of card rarity levels."""
    COMMON = 1
    RARE = 2
    EPIC = 3
    LEGENDARY = 4
    CHAMPION = 5


class CardType(Enum):
    """Enum of card types."""
    TROOP = 1
    BUILDING = 2
    SPELL = 3


class CardInfo(TypedDict):
    """A card's name, rarity, elixir, and type."""
    name: str
    rarity: Rarity
    elixir: int
    type:   CardType


CARD_INFO: Dict[int, CardInfo] = {
    26000000: {"name": "Knight",            "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000001: {"name": "Archers",           "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000002: {"name": "Goblins",           "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.TROOP},
    26000003: {"name": "Giant",             "rarity": Rarity.RARE,      "elixir": 5,    "type": CardType.TROOP},
    26000004: {"name": "P.E.K.K.A",         "rarity": Rarity.EPIC,      "elixir": 7,    "type": CardType.TROOP},
    26000005: {"name": "Minions",           "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000006: {"name": "Balloon",           "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000007: {"name": "Witch",             "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000008: {"name": "Barbarians",        "rarity": Rarity.COMMON,    "elixir": 5,    "type": CardType.TROOP},
    26000009: {"name": "Golem",             "rarity": Rarity.EPIC,      "elixir": 8,    "type": CardType.TROOP},
    26000010: {"name": "Skeletons",         "rarity": Rarity.COMMON,    "elixir": 1,    "type": CardType.TROOP},
    26000011: {"name": "Valkyrie",          "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000012: {"name": "Skeleton Army",     "rarity": Rarity.EPIC,      "elixir": 3,    "type": CardType.TROOP},
    26000013: {"name": "Bomber",            "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.TROOP},
    26000014: {"name": "Musketeer",         "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000015: {"name": "Baby Dragon",       "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.TROOP},
    26000016: {"name": "Prince",            "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000017: {"name": "Wizard",            "rarity": Rarity.RARE,      "elixir": 5,    "type": CardType.TROOP},
    26000018: {"name": "Mini P.E.K.K.A",    "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000019: {"name": "Spear Goblins",     "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.TROOP},
    26000020: {"name": "Giant Skeleton",    "rarity": Rarity.EPIC,      "elixir": 6,    "type": CardType.TROOP},
    26000021: {"name": "Hog Rider",         "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000022: {"name": "Minion Horde",      "rarity": Rarity.COMMON,    "elixir": 5,    "type": CardType.TROOP},
    26000023: {"name": "Ice Wizard",        "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000024: {"name": "Royal Giant",       "rarity": Rarity.COMMON,    "elixir": 6,    "type": CardType.TROOP},
    26000025: {"name": "Guards",            "rarity": Rarity.EPIC,      "elixir": 3,    "type": CardType.TROOP},
    26000026: {"name": "Princess",          "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000027: {"name": "Dark Prince",       "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.TROOP},
    26000028: {"name": "Three Musketeers",  "rarity": Rarity.RARE,      "elixir": 9,    "type": CardType.TROOP},
    26000029: {"name": "Lava Hound",        "rarity": Rarity.LEGENDARY, "elixir": 7,    "type": CardType.TROOP},
    26000030: {"name": "Ice Spirit",        "rarity": Rarity.COMMON,    "elixir": 1,    "type": CardType.TROOP},
    26000031: {"name": "Fire Spirit",       "rarity": Rarity.COMMON,    "elixir": 1,    "type": CardType.TROOP},
    26000032: {"name": "Miner",             "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000033: {"name": "Sparky",            "rarity": Rarity.LEGENDARY, "elixir": 6,    "type": CardType.TROOP},
    26000034: {"name": "Bowler",            "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000035: {"name": "Lumberjack",        "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000036: {"name": "Battle Ram",        "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000037: {"name": "Inferno Dragon",    "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000038: {"name": "Ice Golem",         "rarity": Rarity.RARE,      "elixir": 2,    "type": CardType.TROOP},
    26000039: {"name": "Mega Minion",       "rarity": Rarity.RARE,      "elixir": 3,    "type": CardType.TROOP},
    26000040: {"name": "Dart Goblin",       "rarity": Rarity.RARE,      "elixir": 3,    "type": CardType.TROOP},
    26000041: {"name": "Goblin Gang",       "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000042: {"name": "Electro Wizard",    "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000043: {"name": "Elite Barbarians",  "rarity": Rarity.COMMON,    "elixir": 6,    "type": CardType.TROOP},
    26000044: {"name": "Hunter",            "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.TROOP},
    26000045: {"name": "Executioner",       "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000046: {"name": "Bandit",            "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000047: {"name": "Royal Recruits",    "rarity": Rarity.COMMON,    "elixir": 7,    "type": CardType.TROOP},
    26000048: {"name": "Night Witch",       "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000049: {"name": "Bats",              "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.TROOP},
    26000050: {"name": "Royal Ghost",       "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000051: {"name": "Ram Rider",         "rarity": Rarity.LEGENDARY, "elixir": 5,    "type": CardType.TROOP},
    26000052: {"name": "Zappies",           "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000053: {"name": "Rascals",           "rarity": Rarity.COMMON,    "elixir": 5,    "type": CardType.TROOP},
    26000054: {"name": "Cannon Cart",       "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000055: {"name": "Mega Knight",       "rarity": Rarity.LEGENDARY, "elixir": 7,    "type": CardType.TROOP},
    26000056: {"name": "Skeleton Barrel",   "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000057: {"name": "Flying Machine",    "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000058: {"name": "Wall Breakers",     "rarity": Rarity.EPIC,      "elixir": 2,    "type": CardType.TROOP},
    26000059: {"name": "Royal Hogs",        "rarity": Rarity.RARE,      "elixir": 5,    "type": CardType.TROOP},
    26000060: {"name": "Goblin Giant",      "rarity": Rarity.EPIC,      "elixir": 6,    "type": CardType.TROOP},
    26000061: {"name": "Fisherman",         "rarity": Rarity.LEGENDARY, "elixir": 3,    "type": CardType.TROOP},
    26000062: {"name": "Magic Archer",      "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000063: {"name": "Electro Dragon",    "rarity": Rarity.EPIC,      "elixir": 5,    "type": CardType.TROOP},
    26000064: {"name": "Firecracker",       "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.TROOP},
    26000065: {"name": "Mighty Miner",      "rarity": Rarity.CHAMPION,  "elixir": 4,    "type": CardType.TROOP},
    26000067: {"name": "Elixir Golem",      "rarity": Rarity.RARE,      "elixir": 3,    "type": CardType.TROOP},
    26000068: {"name": "Battle Healer",     "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.TROOP},
    26000069: {"name": "Skeleton King",     "rarity": Rarity.CHAMPION,  "elixir": 4,    "type": CardType.TROOP},
    26000072: {"name": "Archer Queen",      "rarity": Rarity.CHAMPION,  "elixir": 5,    "type": CardType.TROOP},
    26000074: {"name": "Golden Knight",     "rarity": Rarity.CHAMPION,  "elixir": 4,    "type": CardType.TROOP},
    26000077: {"name": "Monk",              "rarity": Rarity.CHAMPION,  "elixir": 5,    "type": CardType.TROOP},
    26000080: {"name": "Skeleton Dragons",  "rarity": Rarity.COMMON,    "elixir": 4,    "type": CardType.TROOP},
    26000083: {"name": "Mother Witch",      "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    26000084: {"name": "Electro Spirit",    "rarity": Rarity.COMMON,    "elixir": 1,    "type": CardType.TROOP},
    26000085: {"name": "Electro Giant",     "rarity": Rarity.EPIC,      "elixir": 7,    "type": CardType.TROOP},
    26000087: {"name": "Phoenix",           "rarity": Rarity.LEGENDARY, "elixir": 4,    "type": CardType.TROOP},
    27000000: {"name": "Cannon",            "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.BUILDING},
    27000001: {"name": "Goblin Hut",        "rarity": Rarity.RARE,      "elixir": 5,    "type": CardType.BUILDING},
    27000002: {"name": "Mortar",            "rarity": Rarity.COMMON,    "elixir": 4,    "type": CardType.BUILDING},
    27000003: {"name": "Inferno Tower",     "rarity": Rarity.RARE,      "elixir": 5,    "type": CardType.BUILDING},
    27000004: {"name": "Bomb Tower",        "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.BUILDING},
    27000005: {"name": "Barbarian Hut",     "rarity": Rarity.RARE,      "elixir": 7,    "type": CardType.BUILDING},
    27000006: {"name": "Tesla",             "rarity": Rarity.COMMON,    "elixir": 4,    "type": CardType.BUILDING},
    27000007: {"name": "Elixir Collector",  "rarity": Rarity.RARE,      "elixir": 6,    "type": CardType.BUILDING},
    27000008: {"name": "X-Bow",             "rarity": Rarity.EPIC,      "elixir": 6,    "type": CardType.BUILDING},
    27000009: {"name": "Tombstone",         "rarity": Rarity.RARE,      "elixir": 3,    "type": CardType.BUILDING},
    27000010: {"name": "Furnace",           "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.BUILDING},
    27000012: {"name": "Goblin Cage",       "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.BUILDING},
    27000013: {"name": "Goblin Drill",      "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.BUILDING},
    28000000: {"name": "Fireball",          "rarity": Rarity.RARE,      "elixir": 4,    "type": CardType.SPELL},
    28000001: {"name": "Arrows",            "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.SPELL},
    28000002: {"name": "Rage",              "rarity": Rarity.EPIC,      "elixir": 2,    "type": CardType.SPELL},
    28000003: {"name": "Rocket",            "rarity": Rarity.RARE,      "elixir": 6,    "type": CardType.SPELL},
    28000004: {"name": "Goblin Barrel",     "rarity": Rarity.EPIC,      "elixir": 3,    "type": CardType.SPELL},
    28000005: {"name": "Freeze",            "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.SPELL},
    28000006: {"name": "Mirror",            "rarity": Rarity.EPIC,      "elixir": 1.5,  "type": CardType.SPELL},
    28000007: {"name": "Lightning",         "rarity": Rarity.EPIC,      "elixir": 6,    "type": CardType.SPELL},
    28000008: {"name": "Zap",               "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.SPELL},
    28000009: {"name": "Poison",            "rarity": Rarity.EPIC,      "elixir": 4,    "type": CardType.SPELL},
    28000010: {"name": "Graveyard",         "rarity": Rarity.LEGENDARY, "elixir": 5,    "type": CardType.SPELL},
    28000011: {"name": "The Log",           "rarity": Rarity.LEGENDARY, "elixir": 2,    "type": CardType.SPELL},
    28000012: {"name": "Tornado",           "rarity": Rarity.EPIC,      "elixir": 3,    "type": CardType.SPELL},
    28000013: {"name": "Clone",             "rarity": Rarity.EPIC,      "elixir": 3,    "type": CardType.SPELL},
    28000014: {"name": "Earthquake",        "rarity": Rarity.RARE,      "elixir": 3,    "type": CardType.SPELL},
    28000015: {"name": "Barbarian Barrel",  "rarity": Rarity.EPIC,      "elixir": 2,    "type": CardType.SPELL},
    28000016: {"name": "Heal Spirit",       "rarity": Rarity.RARE,      "elixir": 1,    "type": CardType.SPELL},
    28000017: {"name": "Giant Snowball",    "rarity": Rarity.COMMON,    "elixir": 2,    "type": CardType.SPELL},
    28000018: {"name": "Royal Delivery",    "rarity": Rarity.COMMON,    "elixir": 3,    "type": CardType.SPELL},
}
"""Elixir and rarity are not provided by the API, so this information must be hardcoded."""


def deck_elixir_info(deck: Set[int]) -> Tuple[float, int]:
    elixir_costs = []

    for card_id in deck:
        elixir_costs.append(CARD_INFO[card_id]["elixir"])

    elixir_costs.sort()
    avg_elixir = sum(elixir_costs) / 8
    avg_elixir = round(avg_elixir, 1)
    cycle_cost = sum(elixir_costs[:4])

    return (avg_elixir, cycle_cost)


def best_performing_decks(clan_tag: str=None, required_matches: int=10) -> List[Deck]:
    """Get a list of the best performing decks ordered from highest win rate to lowest.

    Args:
        clan_tag: If specified, only consider decks used by members of this clan.
        required_matches: Minimum number of matches that a deck must have been used in to be considered.

    Returns:
        A list of Deck sorted from highest win rate to lowest.
    """
    from utils.db_utils import get_database_connection
    database, cursor = get_database_connection()
    days_interval = 35
    now = datetime.datetime.utcnow()
    current_weekday = now.weekday()

    if current_weekday >= 3:
        days_interval += (current_weekday - 2)

    if clan_tag is None:
        query = f"""
            SELECT pvp_battles.won     AS won,
                   deck_lists.card_ids AS cards,
                   users.name          AS name
            FROM   pvp_battles
                   INNER JOIN (SELECT deck_id,
                                      Group_concat(card_id ORDER BY card_id) AS card_ids
                               FROM   deck_cards
                               GROUP  BY deck_id) AS deck_lists
                           ON pvp_battles.deck_id = deck_lists.deck_id
                   INNER JOIN clan_affiliations
                           ON pvp_battles.clan_affiliation_id = clan_affiliations.id
                   INNER JOIN users
                           ON clan_affiliations.user_id = users.id
            WHERE  game_type IN ( 'CW_Battle_1v1', 'CW_Duel_1v1' )
                   AND time > Date_sub(Now(), INTERVAL {days_interval} day)
        """

        cursor.execute(query)
    else:
        query = f"""
            SELECT pvp_battles.won     AS won,
                   deck_lists.card_ids AS cards,
                   users.name          AS name
            FROM   pvp_battles
                   INNER JOIN (SELECT deck_id,
                                      Group_concat(card_id ORDER BY card_id) AS card_ids
                               FROM   deck_cards
                               GROUP  BY deck_id) AS deck_lists
                           ON pvp_battles.deck_id = deck_lists.deck_id
                   INNER JOIN clan_affiliations
                           ON pvp_battles.clan_affiliation_id = clan_affiliations.id
                   INNER JOIN users
                           ON clan_affiliations.user_id = users.id
            WHERE  game_type IN ( 'CW_Battle_1v1', 'CW_Duel_1v1' )
                   AND time > Date_sub(Now(), INTERVAL {days_interval} day)
                   AND clan_affiliation_id IN (SELECT id
                                               FROM   clan_affiliations
                                               WHERE  clan_id = (SELECT id
                                                                 FROM   clans
                                                                 WHERE  tag = %s))
        """
        cursor.execute(query, (clan_tag))

    database.close()

    @dataclass
    class DeckStats:
        """Class used to store intermediate deck statistics while iterating through battles."""
        wins: int = 0
        losses: int = 0
        users: Set[str] = field(default_factory=set)

    all_decks = defaultdict(DeckStats)

    for battle in cursor:
        deck_set = frozenset(int(card_id) for card_id in battle["cards"].split(","))

        if battle["won"]:
            all_decks[deck_set].wins += 1
        else:
            all_decks[deck_set].losses += 1

        all_decks[deck_set].users.add(battle["name"])

    filtered_decks: List[Deck] = []

    for deck, stats in all_decks.items():
        matches_played = stats.wins + stats.losses

        if matches_played < required_matches:
            continue

        avg_elixir, cycle_cost = deck_elixir_info(deck)

        filtered_decks.append(Deck(
            deck,
            stats.wins / matches_played,
            matches_played,
            avg_elixir,
            cycle_cost,
            stats.users
        ))

    filtered_decks.sort(key=lambda x: x.win_rate, reverse=True)
    return filtered_decks


def suggest_war_decks(clan_tag: str=None, required_matches: int=10) -> List[Deck]:
    """Based on the current best performing decks, find a set of 4 unique decks that optimize overall win rate.

    Args:
        clan_tag: If specified, only consider decks used by members of this clan.
        required_matches: Minimum number of matches that a deck must have been used in to be considered.

    Returns:
        Four decks with no shared cards.
    """
    all_decks = best_performing_decks(clan_tag, required_matches)
    best_total_win_rate = 0
    best_war_decks: List[Deck] = []
    num_decks = len(all_decks)

    for i in range(num_decks - 3):
        i_deck = all_decks[i]
        combined_card_set = set(i_deck.deck)

        for j in range(i+1, num_decks - 2):
            j_deck = all_decks[j]

            if j_deck.deck & combined_card_set:
                continue

            combined_card_set |= j_deck.deck

            for k in range(j+1, num_decks - 1):
                k_deck = all_decks[k]

                if k_deck.deck & combined_card_set:
                    continue

                combined_card_set |= k_deck.deck

                for l in range(k+1, num_decks):
                    l_deck = all_decks[l]

                    if l_deck.deck & combined_card_set:
                        continue

                    combined_win_rate = i_deck.win_rate + j_deck.win_rate + k_deck.win_rate + l_deck.win_rate

                    if combined_win_rate > best_total_win_rate:
                        best_total_win_rate = combined_win_rate
                        best_war_decks = [i_deck, j_deck, k_deck, l_deck]

    return sorted(best_war_decks, key=lambda x: x.win_rate, reverse=True)
