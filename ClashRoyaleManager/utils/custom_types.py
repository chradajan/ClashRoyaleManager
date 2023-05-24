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
    NA = "NA"
    EU = "EU"
    ASIA = "ASIA"
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


class SpecialChannel(Enum):
    """Enum of relevant Discord channels."""
    Kicks = "kicks"
    NewMemberInfo = "new_member_info"
    Rules = "rules"
    Strikes = "strikes"


class StrikeType(Enum):
    """Enum of criteria used to determine who receives automated strikes."""
    Decks = "decks"
    Medals = "medals"


class AutomatedRoutine(Enum):
    """Enum of automated routines that can be toggled for primary clans."""
    Reminders = "send_reminders"
    Stats = "track_stats"
    Strikes = "assign_strikes"


class BlockedReason(Enum):
    """Enum of reasons a user was unable to participate in a River Race."""
    MaxParticipation = "max_participation"
    PreviouslyBattled = "previously_battled"
    NotBlocked = None


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
    discord_channel_id: int


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


class KickData(TypedDict):
    """Dictionary containing information about when a user has been kicked from a specific clan."""
    tag: ClanTag
    name: ClanName
    kicks: List[datetime.datetime]


class DatabaseReport(TypedDict):
    """Dictionary containing player report data retrieved from database."""
    discord_name: str
    strikes: int
    kicks: Dict[str, KickData]


class PredictedOutcome(TypedDict):
    """Dictionary containing information about a clan's predicted outcome at the end of the day."""
    tag: ClanTag
    name: ClanName
    current_score: int
    predicted_score: int
    win_rate: float
    expected_decks_to_use: int
    expected_decks_catchup_win_rate: Union[float, None]
    remaining_decks: int
    remaining_decks_catchup_win_rate: Union[float, None]
    completed: bool


class RiverRaceStatus(TypedDict):
    """Dictionary containing information about how many decks a clan has left to use today."""
    tag: ClanTag
    name: ClanName
    total_remaining_decks: int
    active_remaining_decks: int

class Card(TypedDict):
    """Dictionary containing information about an individual card in the game."""
    name: str
    id: int
    level: int
    max_level: int
    url: str

class PvPBattleResult(TypedDict):
    """Dictionary containing information about one player's results of a PvP battle."""
    crowns: int
    elixir_leaked: float
    kt_hit_points: int
    pt1_hit_points: int
    pt2_hit_points: int
    deck: List[Card]

class PvPBattle(TypedDict):
    """Dictionary containing information about a single PvP battle."""
    time: datetime.datetime
    won: bool
    game_type: str
    team_results: PvPBattleResult
    opponent_results: PvPBattleResult

class Duel(TypedDict):
    """Dictionary containing information about a duel."""
    time: datetime.datetime
    won: bool
    battle_wins: int
    battle_losses: int
    battles: List[PvPBattle]

class BoatBattle(TypedDict):
    """Dictionary containing information about a boat battle."""
    time: datetime.datetime
    won: bool
    elixir_leaked: float
    new_towers_destroyed: int
    prev_towers_destroyed: int
    remaining_towers: int
    deck: List[Card]

class Battles(TypedDict):
    """Dictionary containing a user's River Race battles."""
    pvp_battles: List[PvPBattle]
    duels: List[Duel]
    boat_battles: List[BoatBattle]
