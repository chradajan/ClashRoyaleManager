"""Role manager. Gets saved clan and special roles and makes them accessible through ROLE object."""

from typing import Dict, Set, Union

import discord

import utils.db_utils as db_utils
from utils.custom_types import ClanRole, SpecialRole

class RoleManager:
    """Retrieves and stores relevant Discord roles."""

    def __init__(self):
        """Creates roles dictionary."""
        self.roles: Dict[Union[ClanRole, SpecialRole], discord.Role] = {}

    def initialize_roles(self, guild: discord.Guild):
        """If the database is fully initialized, get all relevant roles.

        Args:
            guild: Guild to get roles from.
        """
        self.guild: discord.Guild = guild

        if db_utils.is_initialized():
            for clan_role in ClanRole:
                role_id = db_utils.get_clan_role_id(clan_role)
                role = guild.get_role(role_id)
                self.roles[clan_role] = role

            for special_role in SpecialRole:
                role_id = db_utils.get_special_role_id(special_role)
                role = guild.get_role(role_id)
                self.roles[special_role] = role


    def __getitem__(self, role: Union[ClanRole, SpecialRole]) -> discord.Role:
        """Get specified Discord role.

        Args:
            role: Role type to get.

        Returns:
            Discord role object corresponding to requested role type.
        """
        return self.roles.get(role)


    def get_affiliated_clan_role(self, tag: str) -> discord.Role:
        """Get role affiliated with the specified clan.

        Args:
            tag: Tag of clan to get affiliated role of.

        Returns:
            Discord role object affiliated with specified clan.
        """
        role_id = db_utils.get_clan_affiliated_role_id(tag)
        return self.guild.get_role(role_id)


    def get_all_roles(self) -> Set[discord.Role]:
        """Get all clan roles, special roles, and primary clan roles.

        Returns:
            Set of relevant roles.
        """
        role_set = {role for role in self.roles.values()}
        primary_clans = db_utils.get_primary_clans()

        for clan in primary_clans:
            role_set.add(self.guild.get_role(clan["discord_role_id"]))

        return role_set


ROLE = RoleManager()
"""Global role manager object."""
