"""Bot events cog."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
from log.logger import LOG
from utils.custom_types import SpecialRole
from utils.role_manager import ROLE

class EventsManager(commands.Cog):
    """Special bot events that need to be handled."""

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Give members New role upon joining server."""
        LOG.info(f"{member} joined the server")
        if member.bot:
            return

        await member.add_roles(ROLE[SpecialRole.New])


    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Remove user from database when they leave server."""
        LOG.info(f"{member.display_name} - {member} left the server")
        db_utils.dissociate_discord_info_from_user(member)
