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
    Rules = "rules"
    Visitor = "visitor"
    Admin = "admin"


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
