"""Various utilities for tracking and analyzing Battle Day statistics."""

import datetime
import numpy
from typing import Dict, List, Tuple, Union

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from log.logger import LOG, log_message
from utils.custom_types import (
    Battles,
    BattleStats,
    ClanStrikeInfo,
    DatabaseRiverRaceClan,
    PredictedOutcome,
    RiverRaceClan,
    UserStrikeData
)
from utils.exceptions import GeneralAPIError

def update_clan_battle_day_stats(tag: str, post_race: bool, api_is_broken: bool):
    """Check the battle logs of any users in a clan that have gained medals since the last check.

    Args:
        tag: Tag of clan to check users in.
        post_race: Whether this is occurring during or after a River Race.
        api_is_broken: Whether the API is currently reporting incorrect max card levels.
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

    stats_to_record: List[Tuple[BattleStats, Battles, int]] = []

    for participant in participants:
        player_tag = participant["tag"]

        if player_tag in prior_medal_counts:
            prior_medals, last_check = prior_medal_counts[player_tag]

            if participant["medals"] > prior_medals:
                LOG.info(log_message("Participant has gained medals since last check",
                                     name=participant["name"],
                                     current_medals=participant["medals"],
                                     prior_medals=prior_medals))

                try:
                    stats, battles = clash_utils.get_battle_day_stats(player_tag, tag, last_check, current_time)
                except GeneralAPIError:
                    LOG.warning(log_message("Failed to get stats", player_tag=player_tag, clan_tag=tag, last_check=last_check))
                    continue

                stats_to_record.append((stats, battles, participant["medals"]))

        elif participant["medals"] > 0:
            LOG.info(log_message("New participant has gained medals since last check",
                                 name=participant["name"],
                                 current_medals=participant["medals"],
                                 prior_medals=0))

            try:
                stats, battles = clash_utils.get_battle_day_stats(player_tag, tag, last_clan_check, current_time)
            except GeneralAPIError:
                LOG.warning(log_message("Failed to get stats", player_tag=player_tag, clan_tag=tag, last_check=last_clan_check))
                continue

            stats_to_record.append((stats, battles, participant["medals"]))

    db_utils.record_battle_day_stats(stats_to_record, current_time, api_is_broken)


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


def determine_strikes(clan_strike_data: ClanStrikeInfo) -> List[UserStrikeData]:
    """Determine which users in the specified clan should receive strikes.

    Args:
        clan_strike_data: Data of clan to determine strikes for.

    Returns:
        List of user data for users that should receive a strike.
    """
    river_race_user_data = db_utils.get_river_race_user_data(clan_strike_data["river_race_id"])
    reset_times = clan_strike_data["reset_times"]
    day_keys = ["day_3", "day_4", "day_5", "day_6", "day_7"]
    max_day_index = 3 if clan_strike_data["completed_saturday"] else 4
    strikes: List[UserStrikeData] = []

    for user_data in river_race_user_data:
        should_receive_strike = False

        # Skip any users that were never a part of the clan in this River Race
        if user_data["tracked_since"] is None:
            continue

        # Determine which day to start evaluating from based on when the bot started tracking them
        first_participation_day = 1

        for day_index, reset_time in enumerate(reset_times[1:], 1):
            if user_data["tracked_since"] < reset_time:
                first_participation_day = day_index
                break

        # Iterate through days that user was in the clan and determine if they met their minimum requirement
        for day_index in range(first_participation_day, max_day_index + 1):
            day_key = day_keys[day_index]
            decks_used = user_data[day_key]

            if decks_used is None:
                LOG.warning(log_message("Expected deck usage but received None",
                                        day_key=day_key,
                                        clan_affiliation_id=user_data["clan_affiliation_id"]))
                continue

            if decks_used >= clan_strike_data["strike_threshold"]:
                continue

            LOG.info(log_message("Checking for deck usage exemption",
                                 day_key=day_key,
                                 decks_used=decks_used,
                                 clan_affiliation_id=user_data["clan_affiliation_id"]))

            # Did not meet minimum minimum deck usage
            # First check if they were locked out due to clan reaching participation cap
            if user_data[day_key + "_locked"]:
                LOG.info("User was locked out")
                continue

            # Not locked out, so check if they used outside battles but still had decks left to use in primary clan
            outside_battles = user_data[day_key + "_outside_battles"]

            if outside_battles is not None:
                unused_decks = 4 - (outside_battles + decks_used)

                if unused_decks == 0:
                    LOG.info("Outside battles detected but user had no remaining decks")
                    continue

            # Don't give strike if they were not in the clan this day
            was_in_clan = False

            if not user_data[day_key + "_active"] and decks_used == 0:
                clan_times = db_utils.get_clan_times(user_data["clan_affiliation_id"])

                if not clan_times:
                    LOG.warning("Expected clan times but received empty list")
                    continue

                day_start = reset_times[day_index - 1]
                day_end = reset_times[day_index]

                for clan_time_start, clan_time_end in clan_times:
                    if ((clan_time_start < day_start and clan_time_end is None) or
                        (clan_time_start < day_start < clan_time_end) or
                        (day_start < clan_time_start < day_end)):
                        LOG.info(log_message("User was active in clan on this day",
                                             day_start=day_start,
                                             day_end=day_end,
                                             clan_time_start=clan_time_start,
                                             clan_time_end=clan_time_end))
                        was_in_clan = True
                        break

                if not was_in_clan:
                    continue

            # No valid excuses found, so assign strike
            should_receive_strike = True
            break

        if should_receive_strike:
            name, tag = db_utils.get_name_and_tag_from_affiliation(user_data["clan_affiliation_id"])

            if name is None:
                LOG.warning("Unable to get name and tag from affiliation id")
                continue

            strikes.append(
                {
                    "name": name,
                    "tag": tag,
                    "tracked_since": user_data["tracked_since"],
                    "deck_usage": [user_data[key] for key in ["day_4", "day_5", "day_6", "day_7"]]
                }
            )

    return strikes


def average_medals_per_deck(win_rate: float) -> float:
    """Get the average medals per deck value at the specified win rate.

    Assumes the player always plays 4 battles by playing a duel followed by normal matches (no boat battles). It's also assumed that
    win rate is the same in duels and normal matches.

    Medals per deck of a player that completes 4 battles with these assumptions can be calculated as
    F(p) = -25p^3 + 25p^2 + 125p + 100 where F(p) is medals per deck and p is probability of winning any given match (win rate). This
    was determined by calculating the expected number of duel matches played in a Bo3 at a given win rate, then subtracting that
    from 4 to determine how many normal matches are played. These quantities are then multiplied by the average amount of medals a
    deck is worth in each game mode. This is equal to f = 250p + 100(1-p) for duels and f = 200p + 100(1-p) for normal matches.

    Args:
        win_rate: Player win rate in PvP matches.

    Returns:
        Average medals per deck used.
    """
    return (-25 * win_rate**3) + (25 * win_rate**2) + (125 * win_rate) + 100


def calculate_win_rate_from_average_medals(avg_medals_per_deck: float) -> float:
    """Solve the polynomial described in average_medals_per_deck.

    Determine what win rate is needed to achieve the specified medals per deck. All assumptions described above hold true here as
    well. If no roots can be determined, then None is returned.

    Args:
        avg_medals_per_deck: Average medals per deck to calculate win rate of.

    Returns:
        Win rate needed to achieve the specified average medals per deck, or None if no solution exists.
    """
    roots = numpy.roots([-25, 25, 125, (100 - avg_medals_per_deck)])
    win_rate = None

    for root in roots:
        if 0 <= root <= 1:
            win_rate = root

    return win_rate


def predict_race_outcome(tag: str, historical_win_rates: bool, historical_deck_usage: bool) -> List[PredictedOutcome]:
    """Predict the outcome of the current Battle Day.

    Returns:
        List of each clan's predicted outcome for today sorted from first to last.

    Raises:
        GeneralAPIError: Something went wrong with the request.
    """
    database_clan_data = db_utils.get_current_season_river_race_clans(tag)
    current_clan_data = clash_utils.get_clans_in_race(tag, False)
    medals_per_deck: Dict[str, float] = {}
    expected_deck_usage: Dict[str, int] = {}
    predicted_outcomes: List[PredictedOutcome] = []
    is_colosseum_week = db_utils.is_colosseum_week(tag)

    if not database_clan_data:
        LOG.error(f"No saved River Race clans for {tag} to make prediction")
        db_utils.update_river_race_clans(tag)
        return predicted_outcomes
    elif database_clan_data.keys() != current_clan_data.keys():
        LOG.error(log_message("Mismatch between saved and current River Race clans",
                              tag=tag,
                              database_clan_data=database_clan_data,
                              current_clan_data=current_clan_data))
        return predicted_outcomes

    combined_data: Dict[str, Tuple[DatabaseRiverRaceClan, RiverRaceClan]] =\
        {clan_tag: (database_clan_data[clan_tag], current_clan_data[clan_tag]) for clan_tag in current_clan_data}

    for clan_tag, (saved_clan_data, current_clan_data) in combined_data.items():
        # Calculate each clan's average medals per deck
        if historical_win_rates:
            total_decks = current_clan_data["decks_used_today"] + saved_clan_data["total_season_battle_decks"]
            total_medals = ((current_clan_data["medals"] - saved_clan_data["current_race_medals"]) +
                            saved_clan_data["total_season_medals"])

            if total_decks == 0:
                medals_per_deck[clan_tag] = 165.625
            else:
                medals_per_deck[clan_tag] = total_medals / total_decks
        else:
            medals_per_deck[clan_tag] = 165.625

        current_decks_used_today = current_clan_data["decks_used_today"]

        # Calculate expected number of decks for each to clan to use
        if historical_deck_usage:
            if saved_clan_data["battle_days"] == 0:
                expected_decks_left = 200 - current_decks_used_today
            else:
                avg_deck_usage = round(saved_clan_data["total_season_battle_decks"] / saved_clan_data["battle_days"])

                if current_decks_used_today > avg_deck_usage:
                    expected_decks_left = round((200 - current_decks_used_today) * 0.25)
                else:
                    expected_decks_left = avg_deck_usage - current_decks_used_today

            expected_deck_usage[clan_tag] = expected_decks_left
        else:
            expected_deck_usage[clan_tag] = 200 - current_decks_used_today
    
    # Calculate predicted scores
    for clan_tag, (saved_clan_data, current_clan_data) in combined_data.items():
        base_medals = current_clan_data["medals"] - (0 if is_colosseum_week else saved_clan_data["current_race_medals"])
        predicted_score = 50 * round((base_medals + (expected_deck_usage[clan_tag] * medals_per_deck[clan_tag])) / 50)

        predicted_outcome: PredictedOutcome = {
            "tag": clan_tag,
            "name": current_clan_data["name"],
            "current_score": base_medals,
            "predicted_score": predicted_score,
            "win_rate": calculate_win_rate_from_average_medals(medals_per_deck[clan_tag]),
            "expected_decks_to_use": expected_deck_usage[clan_tag],
            "expected_decks_catchup_win_rate": None,
            "remaining_decks": 200 - current_clan_data["decks_used_today"],
            "remaining_decks_catchup_win_rate": None,
            "completed": current_clan_data["completed"] and not is_colosseum_week
        }

        if predicted_outcome["win_rate"] is None:
            predicted_outcome["win_rate"] = 0

        predicted_outcomes.append(predicted_outcome)

    predicted_outcomes.sort(key=lambda x: x["predicted_score"], reverse=True)
    winning_score = predicted_outcomes[0]["predicted_score"]

    # Calculate win rates needed for clans not in first place to catch up
    for predicted_outcome in predicted_outcomes[1:]:
        clan_tag = predicted_outcome["tag"]
        medals_to_reach_first = winning_score - predicted_outcome["current_score"]

        if expected_deck_usage[clan_tag] == 0:
            expected_usage_avg_medals_needed = 1000
        else:
            expected_usage_avg_medals_needed = medals_to_reach_first / expected_deck_usage[clan_tag]

        if predicted_outcome["remaining_decks"] == 0:
            all_usage_avg_medals_needed = 1000
        else:
            all_usage_avg_medals_needed = medals_to_reach_first / predicted_outcome["remaining_decks"]

        if expected_usage_avg_medals_needed < 100:
            predicted_outcome["expected_decks_catchup_win_rate"] = -1
        else:
            predicted_outcome["expected_decks_catchup_win_rate"] =\
                calculate_win_rate_from_average_medals(expected_usage_avg_medals_needed)

        if all_usage_avg_medals_needed < 100:
            predicted_outcome["remaining_decks_catchup_win_rate"] = -1
        else:
            predicted_outcome["remaining_decks_catchup_win_rate"] =\
                calculate_win_rate_from_average_medals(all_usage_avg_medals_needed)

    return predicted_outcomes
