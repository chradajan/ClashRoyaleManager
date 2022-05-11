"""Main entry point. Creates the bot and runs indefinitely."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
from config.credentials import BOT_TOKEN
from groups.member_commands import MemberCommands

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
    bot.tree.add_command(MemberCommands(), guild=guild)

    @bot.event
    async def on_ready():
        await bot.tree.sync(guild=guild)
        print("Bot Ready")

    bot.run(BOT_TOKEN)


if __name__== "__main__":
    main()
