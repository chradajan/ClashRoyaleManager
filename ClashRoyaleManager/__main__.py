"""Main entry point. Creates the bot and runs indefinitely."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
from cogs.automated_routines import AutomatedRoutines
from cogs.listeners  import EventsManager
from commands.automation_commands import AUTOMATION_COMMANDS
from commands.context_menus import CONTEXT_MENUS
from commands.leader_util_commands import LEADER_UTIL_COMMANDS
from commands.river_race_commands import RIVER_RACE_COMMANDS
from commands.setup_commands import SETUP_COMMANDS
from commands.stat_commands import STAT_COMMANDS
from commands.status_reports import STATUS_REPORT_COMMANDS
from commands.strike_commands import STRIKE_COMMANDS
from commands.update_commands import UPDATE_COMMANDS
from config.credentials import BOT_TOKEN
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.role_manager import ROLE

ON_READY_CALLED = False

def main():
    """Start ClashRoyaleManager."""
    guild_id = db_utils.get_guild_id()
    guild = discord.Object(id=guild_id)
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    activity = discord.Game(name="Clash Royale")
    bot = commands.Bot(command_prefix='!',
                       activity=activity,
                       help_command=None,
                       intents=intents)

    pre_initialization_groups = [*SETUP_COMMANDS]
    post_initialization_groups = [
        *AUTOMATION_COMMANDS,
        *CONTEXT_MENUS,
        *LEADER_UTIL_COMMANDS,
        *RIVER_RACE_COMMANDS,
        *STAT_COMMANDS,
        *STATUS_REPORT_COMMANDS,
        *STRIKE_COMMANDS,
        *UPDATE_COMMANDS
    ]

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
        global ON_READY_CALLED

        if ON_READY_CALLED:
            LOG.debug("On ready called again after initial startup")
            return

        await bot.tree.sync(guild=guild)
        CHANNEL.initialize_channels(bot.get_guild(guild_id))
        ROLE.initialize_roles(bot.get_guild(guild_id))

        if db_utils.is_initialized():
            await bot.add_cog(AutomatedRoutines(bot.get_guild(guild_id)))
            await bot.add_cog(EventsManager())

        LOG.info("Bot started")
        print("Bot Ready")
        ON_READY_CALLED = True

    bot.run(BOT_TOKEN)


if __name__== "__main__":
    main()
