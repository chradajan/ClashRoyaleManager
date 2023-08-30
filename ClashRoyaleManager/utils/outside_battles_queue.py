"""List of warnings to send to NewMemberInfo when a user joins a clan on a war day after battling for a different clan."""

from typing import List, Tuple

from utils.custom_types import ClashData

UNSENT_WARNINGS: List[Tuple[ClashData, int]] = []
"""List of data to be sent."""
