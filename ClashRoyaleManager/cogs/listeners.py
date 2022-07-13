"""Bot events cog."""

import discord
from discord.ext import commands

import utils.db_utils as db_utils
import utils.kick_utils as kick_utils
from log.logger import LOG, log_message
from utils.channel_manager import CHANNEL
from utils.custom_types import SpecialChannel, SpecialRole
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


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check for kick screenshots."""
        if message.channel == CHANNEL[SpecialChannel.Rules] and not message.author.guild_permissions.administrator:
            try:
                await message.delete()
            except Exception as e:
                LOG.exception(e)
        elif message.attachments and (message.channel == CHANNEL[SpecialChannel.Kicks]) and not message.author.bot:
            for attachment in message.attachments:
                if attachment.content_type in {'image/png', 'image/jpeg'}:
                    tag, name = await kick_utils.get_player_info_from_image(attachment)
                    LOG.info(log_message("Parsed data from kick screenshot", tag=tag, name=name))

                    if tag is None:
                        embed = discord.Embed(title="Unable to parse player info from screenshot.",
                                              description="You can still log this kick manually with the `/kick` command.",
                                              color=discord.Color.red())
                        view = None
                    else:
                        embed = discord.Embed(title=f"Did you just kick {name}?", color=discord.Color.random())
                        view = kick_utils.KickView(tag, name)

                    await message.channel.send(embed=embed, view=view)
