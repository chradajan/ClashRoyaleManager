"""Custom types used by ClashRoyaleManager."""

import datetime
from enum import auto, Enum
from typing import (
    Dict,
    List,
    Tuple,
    TypedDict,
    Union
)

class ReminderTime(Enum):
    """Valid times to receive automated reminders."""
    US = "US"
    EU = "EU"
    ALL = "ALL"


class ClanRole(Enum):
    """Enum of possible clan roles."""
    Member = "member"
    Elder = "elder"
    Coleader = "coleader"
    Leader = "leader"


class SpecialRole(Enum):
    """Enum of relevant Discord roles that are not clan roles."""
    New = "new"
    Visitor = "visitor"
    Admin = "admin"


class SpecialChannel(Enum):
    """Enum of relevant Discord channels."""
    Strikes = "strikes"
    Reminders = "reminders"
    AdminOnly = "admin_only"


class StrikeCriteria(Enum):
    """Enum of criteria used to determine who receives automated strikes."""
    Decks = "decks"
    Medals = "medals"


class ClashData(TypedDict):
    """Dictionary containing data about user from the Clash Royale API."""
    tag: str
    name: str
    role: Union[ClanRole, None]
    exp_level: int
    trophies: int
    best_trophies: int
    cards: Dict[int, int]
    found_cards: int
    total_cards: int
    clan_name: Union[str, None]
    clan_tag: Union[str, None]


class PrimaryClan(TypedDict):
    """Dictionary containing information about a primary clan."""
    tag: str
    name: str
    id: int
    discord_role_id: int
    track_stats: bool
    send_reminders: bool
    assign_strikes: bool
    strike_type: StrikeCriteria
    strike_threshold: int


class RiverRaceInfo(TypedDict):
    """Information about a clan's current River Race."""
    tag: str
    name: str
    start_time: datetime.datetime
    colosseum_week: bool
    completed_saturday: bool
    week: int
    clans: List[Tuple[str, str]] # (tag, name)


class RiverRaceClan(TypedDict):
    """Dictionary containing data about a clan's stats in a river race."""
    tag: str
    name: str
    medals: int
    total_decks_used: int
    decks_used_today: int
    completed: bool


class Participant(TypedDict):
    """Dictionary containing data about a participant in a river race."""
    tag: str
    name: str
    medals: int
    repair_points: int
    boat_attacks: int
    decks_used: int
    decks_used_today: int


class BattleStats(TypedDict):
    """Dictionary containing a user's wins/losses on Battle Days."""
    player_tag: str
    clan_tag: str
    regular_wins: int
    regular_losses: int
    special_wins: int
    special_losses: int
    duel_wins: int
    duel_losses: int
    series_wins: int
    series_losses: int
    boat_wins: int
    boat_losses: int


class DatabaseRiverRaceClan(TypedDict):
    """Dictionary containing fields in river_race_clans table."""
    id: int
    clan_id: int
    season_id: int
    tag: str
    name: str
    current_race_medals: int
    total_season_medals: int
    current_race_total_decks: int
    total_season_battle_decks: int
    battle_days: int


class DecksReport(TypedDict):
    """Dictionary containing a report of deck usage today."""
    remaining_decks: int
    participants: int
    active_members_with_no_decks_used: int
    active_members_with_remaining_decks: List[Tuple[str, str, int]]     # (tag, name, decks_remaining)
    active_members_without_remaining_decks: List[Tuple[str, str, int]]  # (tag, name, decks_remaining)
    inactive_members_with_decks_used: List[Tuple[str, str, int]]        # (tag, name, decks_remaining)
    locked_out_active_members: List[Tuple[str, str, int]]               # (tag, name, decks_remaining)
