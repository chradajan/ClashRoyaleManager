"""Bot events cog."""

import discord
from discord.ext import commands

class Events(commands.Cog):
    """Special bot events that need to be handled."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
