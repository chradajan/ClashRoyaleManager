"""Custom types used by ClashRoyaleManager."""

import datetime
from enum import Enum
from typing import (
    Dict,
    List,
    Tuple,
    TypedDict,
    Union
)

PlayerTag = str
PlayerName = str
ClanTag = str
ClanName = str
DecksRemaining = int


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


class StrikeType(Enum):
    """Enum of criteria used to determine who receives automated strikes."""
    Decks = "decks"
    Medals = "medals"


class AutomatedRoutine(Enum):
    """Enum of automated routines that can be toggled for primary clans."""
    Reminders = "send_reminders"
    Stats = "track_stats"
    Strikes = "assign_strikes"


class ClashData(TypedDict):
    """Dictionary containing data about user from the Clash Royale API."""
    tag: PlayerTag
    name: PlayerName
    role: Union[ClanRole, None]
    exp_level: int
    trophies: int
    best_trophies: int
    cards: Dict[int, int]
    found_cards: int
    total_cards: int
    clan_tag: Union[ClanTag, None]
    clan_name: Union[ClanName, None]


class PrimaryClan(TypedDict):
    """Dictionary containing information about a primary clan."""
    tag: ClanTag
    name: ClanName
    id: int
    discord_role_id: int
    track_stats: bool
    send_reminders: bool
    assign_strikes: bool
    strike_type: StrikeType
    strike_threshold: int


class RiverRaceInfo(TypedDict):
    """Information about a clan's current River Race."""
    tag: ClanTag
    name: ClanName
    start_time: datetime.datetime
    colosseum_week: bool
    completed_saturday: bool
    week: int
    clans: List[Tuple[ClanTag, ClanName]]


class RiverRaceClan(TypedDict):
    """Dictionary containing data about a clan's stats in a river race."""
    tag: ClanTag
    name: ClanName
    medals: int
    total_decks_used: int
    decks_used_today: int
    completed: bool


class Participant(TypedDict):
    """Dictionary containing data about a participant in a river race."""
    tag: PlayerTag
    name: PlayerName
    medals: int
    repair_points: int
    boat_attacks: int
    decks_used: int
    decks_used_today: int


class BattleStats(TypedDict):
    """Dictionary containing a user's wins/losses on Battle Days."""
    player_tag: PlayerTag
    clan_tag: ClanTag
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
    tag: ClanTag
    name: ClanName
    current_race_medals: int
    total_season_medals: int
    current_race_total_decks: int
    total_season_battle_decks: int
    battle_days: int


class DecksReport(TypedDict):
    """Dictionary containing a report of deck usage today."""
    remaining_decks: DecksRemaining
    participants: int
    active_members_with_no_decks_used: int
    active_members_with_remaining_decks: List[Tuple[PlayerTag, PlayerName, DecksRemaining]]
    active_members_without_remaining_decks: List[Tuple[PlayerTag, PlayerName, DecksRemaining]]
    inactive_members_with_decks_used: List[Tuple[PlayerTag, PlayerName, DecksRemaining]]
    locked_out_active_members: List[Tuple[PlayerTag, PlayerName, DecksRemaining]]


class UserStrikeInfo(TypedDict):
    """Dictionary of data needed to determine whether a user should receive a strike."""
    discord_id: int
    name: PlayerName
    tracked_since: datetime.datetime
    medals: int
    deck_usage: List[Union[int, None]]


class ClanStrikeInfo(TypedDict):
    """Dictionary of data needed to determine who in a clan should receive a strike."""
    strike_type: StrikeType
    strike_threshold: int
    completed_saturday: bool
    reset_times: List[datetime.datetime]
    users: Dict[PlayerTag, UserStrikeInfo]
