"""Create views for handling kick screenshots."""

import os
import re
from difflib import SequenceMatcher
from typing import List, Tuple, Union

import cv2
import discord
import pytesseract

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from log.logger import LOG
from utils.custom_types import Participant
from utils.exceptions import GeneralAPIError

PRIMARY_CLANS = db_utils.get_primary_clans()

def parse_image_text(text: str) -> Tuple[Union[str, None], Union[str, None]]:
    """Parse text for a player tag and/or player name.

    Args:
        text: Text parsed from a screenshot.

    Returns:
        Tuple of player tag if found (otherwise None) and player name if found (otherwise None).
    """
    tag = re.search(r"(#[A-Z0-9]+)", text)

    if tag is not None:
        tag = tag.group(1)
    else:
        tag = None

    name = re.search(r"(?i)kick (.*) out of the clan\?", text)

    if name is not None:
        name = name.group(1)
    else:
        name = None

    return (tag, name)


async def get_player_info_from_image(image: discord.Attachment) -> Tuple[Union[str, None], Union[str, None]]:
    """Parse a kick screenshot for a player name and/or player tag.

    Args:
        image: Image of in-game kick screenshot.

    Returns:
        Tuple of closest matching player tag and player name from screenshot.
    """
    participants: List[Participant] = []

    for clan in PRIMARY_CLANS:
        try:
            if db_utils.is_battle_time(clan["tag"]):
                participants += clash_utils.get_river_race_participants(clan["tag"])
            else:
                participants += clash_utils.get_prior_river_race_participants(clan["tag"])
        except GeneralAPIError:
            LOG.warning("Failed to get participants while parsing kick screenshot")
            continue

    if not participants:
        return (None, None)

    file_path = "kick_images"

    if not os.path.exists(file_path):
        os.makedirs(file_path)

    file_path += '/' + image.filename
    await image.save(file_path)
    img = cv2.imread(file_path)
    text = pytesseract.image_to_string(img)
    os.remove(file_path)

    tag, name = parse_image_text(text)
    closest_tag = None
    closest_name = None
    highest_tag_similarity = 0
    highest_name_similarity = 0

    for participant in participants:
        active_tag = participant["tag"]
        active_name = participant["name"]

        if tag is not None:
            temp_tag_similarity = SequenceMatcher(None, tag, active_tag).ratio()
            if temp_tag_similarity > highest_tag_similarity:
                highest_tag_similarity = temp_tag_similarity
                closest_tag = active_tag

                if name is None:
                    closest_name = active_name

        if name is not None:
            temp_name_similarity = SequenceMatcher(None, name, active_name).ratio()

            if temp_name_similarity > highest_name_similarity:
                highest_name_similarity = temp_name_similarity
                closest_name = active_name

                if tag is None:
                    closest_tag = active_tag

    return_info = (closest_tag, closest_name)

    if tag is not None and name is not None:
        for participant in participants:
            if participant["tag"] != closest_tag:
                continue
            if participant["name"] != closest_name:
                return_info = (None, None)
            break

    return return_info


class KickButton(discord.ui.Button):
    """Button used to associate a kick with a clan."""

    def __init__(self, clan_tag: str, clan_name: str, player_tag: str, player_name: str):
        """Initialize kick button.

        Args:
            clan_tag: Tag of clan to optionally kick user from.
            clan_name: Name of clan to optionally kick user from.
            player_tag: Tag of user being kicked.
            player_name: Name of user being kicked.
        """
        super().__init__(label=clan_name)
        self.clan_tag = clan_tag
        self.clan_name = clan_name
        self.player_tag = player_tag
        self.player_name = player_name

    async def callback(self, interaction: discord.Interaction):
        """Callback when button is clicked to log kick."""
        db_utils.kick_user(self.player_tag, self.clan_tag)
        embed = discord.Embed(title=f"{self.player_name} was kicked from {self.clan_name}", color=discord.Color.random())
        await interaction.response.edit_message(embed=embed, view=None)


class KickDeleteButton(discord.ui.Button):
    """Button used to delete the kick view if no kick should be logged."""

    def __init__(self, player_name: str):
        """Initialize delete button.

        Args:
            player_name: Name of player that would've been kicked.
        """
        super().__init__(label="X", style=discord.ButtonStyle.danger)
        self.player_name = player_name

    async def callback(self, interaction: discord.Interaction):
        """Callback when button is clicked to delete view."""
        embed = discord.Embed(title=f"No kick logged for {self.player_name}", color=discord.Color.random())
        await interaction.response.edit_message(embed=embed, view=None)


class KickView(discord.ui.View):
    """View that manages buttons for logging a kicked user."""

    def __init__(self, player_tag: str, player_name: str):
        """Initialize kick view.

        Args:
            player_tag: Tag of user being kicked.
            player_name: Name of user being kicked.
        """
        super().__init__()

        for clan in PRIMARY_CLANS:
            self.add_item(KickButton(clan['tag'], clan['name'], player_tag, player_name))

        self.add_item(KickDeleteButton(player_name))
