"""Various utility functions for Discord related needs."""

import discord

import utils.db_utils as db_utils
from utils.custom_types import SpecialRole
from utils.role_manager import ROLE

def full_discord_name(member: discord.Member) -> str:
    """Get the full username of a Discord member. This includes username and discriminator.

    Args:
        member: Member to get full name of.

    Returns:
        Specified member's full name.
    """
    return member.name + '#' + member.discriminator


async def assign_roles(member: discord.Member):
    """Assign proper roles to user based on their clan affiliation and clan role. Should not be used for a member with the New role.

    Args:
        member: Member to fix roles of.
    """
    clan_affiliation = db_utils.get_clan_affiliation(member)

    if clan_affiliation is None:
        correct_roles = {ROLE[SpecialRole.Visitor]}
    else:
        clan_tag, in_primary_clan, clan_role = clan_affiliation
        if in_primary_clan:
            correct_roles = {
                ROLE.get_affiliated_clan_role(clan_tag),
                ROLE[clan_role]
            }
        else:
            correct_roles = {ROLE[SpecialRole.Visitor]}

    current_roles = set(member.roles).intersection(ROLE.get_all_roles())
    await member.remove_roles(*list(current_roles - correct_roles))
    await member.add_roles(*list(correct_roles))
