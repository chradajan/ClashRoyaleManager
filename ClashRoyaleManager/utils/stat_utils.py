"""Various utilities for tracking and analyzing Battle Day statistics."""

from typing import List

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from log.logger import LOG, log_message
from utils.custom_types import BattleStats, DatabaseRiverRaceClan
from utils.exceptions import GeneralAPIError

def update_clan_battle_day_stats(tag: str, post_race: bool):
    """Check the battle logs of any users in a clan that have gained medals since the last check.

    Args:
        tag: Tag of clan to check users in.
        post_race: Whether this is occurring during or after a River Race.
    """
    db_utils.add_unregistered_users(tag)

    if post_race:
        participants = clash_utils.get_prior_river_race_participants(tag)
    else:
        participants = clash_utils.get_river_race_participants(tag)

    prior_medal_counts = db_utils.get_medal_counts(tag)
    last_clan_check = db_utils.get_last_check(tag)
    current_time = db_utils.set_last_check(tag)

    if post_race:
        current_time = db_utils.get_most_recent_reset_time(tag)

    stats_to_record: List[BattleStats] = []

    for participant in participants:
        player_tag = participant["tag"]

        if player_tag in prior_medal_counts:
            prior_medals, last_check = prior_medal_counts[player_tag]

            if participant["medals"] > prior_medals:
                try:
                    stats = clash_utils.get_battle_day_stats(player_tag, tag, last_check, current_time)
                except GeneralAPIError:
                    LOG.warning(log_message("Failed to get stats", player_tag=player_tag, clan_tag=tag, last_check=last_check))
                    continue

                stats_to_record.append((stats, participant["medals"]))

        elif participant["medals"] > 0:
            try:
                stats = clash_utils.get_battle_day_stats(player_tag, tag, last_clan_check, current_time)
            except GeneralAPIError:
                LOG.warning(log_message("Failed to get stats", player_tag=player_tag, clan_tag=tag, last_check=last_clan_check))
                continue

            stats_to_record.append((stats, participant["medals"]))

    db_utils.record_battle_day_stats(stats_to_record)


def save_river_race_clans_info(tag: str, post_race: bool):
    """Update all clans in the specified clan's river_race_clans table entries.

    Args:
        tag: Tag of clan to update data for.
        post_race: Whether this is occurring during or after a River Race.
    """
    try:
        current_clan_data = clash_utils.get_clans_in_race(tag, post_race)
    except GeneralAPIError:
        LOG.warning(log_message("Unable to get clans in race", tag=tag, post_race=post_race))
        return

    saved_clan_data = db_utils.get_current_season_river_race_clans(tag)
    is_colosseum_week = db_utils.is_colosseum_week(tag)
    data_to_save: List[DatabaseRiverRaceClan] = []

    for tag, current_data in current_clan_data.items():
        if post_race and current_data["completed"] and not is_colosseum_week:
            continue

        saved_data = saved_clan_data[tag]
        updated_data = saved_data.copy()
        medals_earned_today = current_data["medals"] - saved_data["current_race_medals"]
        current_race_total_decks = current_data["total_decks_used"]
        battle_decks_used_today = current_race_total_decks - saved_data["current_race_total_decks"]

        updated_data["current_race_medals"] = current_data["medals"]
        updated_data["total_season_medals"] += medals_earned_today
        updated_data["current_race_total_decks"] = current_race_total_decks
        updated_data["total_season_battle_decks"] += battle_decks_used_today
        updated_data["battle_days"] += 1
        data_to_save.append(updated_data)

    db_utils.update_current_season_river_race_clans(data_to_save)
