"""Custom types used by ClashRoyaleManager."""

from enum import auto, Enum
from typing import Dict, TypedDict, Union

class ReminderTime(Enum):
    """Valid times to receive automated reminders."""
    US = "US"
    EU = "EU"
    ALL = "ALL"


class ClanRole(Enum):
    """Enum of possible clan roles."""
    MEMBER = "member"
    ELDER = "elder"
    COLEADER = "coleader"
    LEADER = "leader"


class SpecialRoles(Enum):
    """Enum of relevant Discord roles that are not clan roles."""
    NEW = "new"
    RULES = "rules"
    VISITOR = "visitor"


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
