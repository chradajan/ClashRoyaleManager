"""Channel manager. Gets saved special channels and makes them accessible through CHANNEL object."""

from typing import Dict

import discord

import utils.db_utils as db_utils
from utils.custom_types import SpecialChannel

class ChannelManager:
    """Retrieves and stores relevant Discord channels."""

    def __init__(self):
        """Create channels dictionary."""
        self.channels: Dict[SpecialChannel, discord.TextChannel] = {}


    def initialize_channels(self, guild: discord.Guild):
        """If the database is fully initialized, get all special channels.

        Args:
            guild: Guild to get channels from.
        """
        if db_utils.is_initialized():
            for special_channel in SpecialChannel:
                channel_id = db_utils.get_special_channel_id(special_channel)
                channel = guild.get_channel(channel_id)
                self.channels[special_channel] = channel


    def __getitem__(self, special_channel: SpecialChannel) -> discord.TextChannel:
        """Get specified Discord channel.

        Args:
            special_channel: Channel type to get.

        Returns:
            Discord channel object corresponding to requested channel type.
        """
        return self.channels.get(special_channel)


CHANNEL = ChannelManager()
"""Global channel manager object."""
