"""Main entry point. Creates the bot and runs indefinitely."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
from cogs.listeners  import EventsManager
from config.credentials import BOT_TOKEN
from groups.member_commands import MEMBER_COMMANDS
from groups.setup_commands import SETUP_COMMANDS
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.role_manager import ROLE

def main():
    """Start ClashRoyaleManager."""
    guild_id = db_utils.get_guild_id()
    guild = discord.Object(id=guild_id)
    intents = discord.Intents.default()
    intents.members = True
    activity = discord.Game(name="Clash Royale")
    bot = commands.Bot(command_prefix='!',
                       activity=activity,
                       help_command=None,
                       intents=intents)

    pre_initialization_groups = [*SETUP_COMMANDS]
    post_initialization_groups = [*MEMBER_COMMANDS]

    if db_utils.is_initialized():
        for command in pre_initialization_groups:
            bot.tree.remove_command(command, guild=guild)

        for command in post_initialization_groups:
            bot.tree.add_command(command, guild=guild)
    else:
        for command in post_initialization_groups:
            bot.tree.remove_command(command, guild=guild)

        for command in pre_initialization_groups:
            bot.tree.add_command(command, guild=guild)

    @bot.event
    async def on_ready():
        await bot.tree.sync(guild=guild)
        CHANNEL.initialize_channels(bot.get_guild(guild_id))
        ROLE.initialize_roles(bot.get_guild(guild_id))

        if db_utils.is_initialized():
            await bot.add_cog(EventsManager())

        LOG.info("Bot started")
        print("Bot Ready")

    bot.run(BOT_TOKEN)


if __name__== "__main__":
    main()
