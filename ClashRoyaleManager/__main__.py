"""Main entry point. Creates the bot and runs indefinitely."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
from config.credentials import BOT_TOKEN
from groups.member_commands import MemberCommands
from groups.setup_commands import SetupCommands

def main():
    """Start ClashRoyaleManager."""
    guild = discord.Object(id=db_utils.get_guild_id())
    intents = discord.Intents.default()
    intents.members = True
    activity = discord.Game(name="Clash Royale")
    bot = commands.Bot(command_prefix='!',
                       activity=activity,
                       help_command=None,
                       intents=intents)

    pre_initialization_groups = [SetupCommands]
    post_initialization_groups = [MemberCommands]

    if db_utils.is_initialized():
        for group in pre_initialization_groups:
            bot.tree.remove_command(group(), guild=guild)

        for group in post_initialization_groups:
            bot.tree.add_command(group(), guild=guild)
    else:
        for group in post_initialization_groups:
            bot.tree.remove_command(group(), guild=guild)

        for group in pre_initialization_groups:
            bot.tree.add_command(group(), guild=guild)

    @bot.event
    async def on_ready():
        await bot.tree.sync(guild=guild)
        print("Bot Ready")

    bot.run(BOT_TOKEN)


if __name__== "__main__":
    main()
