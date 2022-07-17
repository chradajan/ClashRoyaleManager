"""Various utilities for tracking and analyzing Battle Day statistics."""

import datetime
import numpy
from typing import Dict, List, Tuple, Union

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
from log.logger import LOG, log_message
from utils.custom_types import BattleStats, ClanStrikeInfo, DatabaseRiverRaceClan, PredictedOutcome, RiverRaceClan, StrikeType
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
                LOG.info(log_message("Participant has gained medals since last check",
                                     name=participant["name"],
                                     current_medals=participant["medals"],
                                     prior_medals=prior_medals))

                try:
                    stats = clash_utils.get_battle_day_stats(player_tag, tag, last_check, current_time)
                except GeneralAPIError:
                    LOG.warning(log_message("Failed to get stats", player_tag=player_tag, clan_tag=tag, last_check=last_check))
                    continue

                stats_to_record.append((stats, participant["medals"]))

        elif participant["medals"] > 0:
            LOG.info(log_message("New participant has gained medals since last check",
                                 name=participant["name"],
                                 current_medals=participant["medals"],
                                 prior_medals=0))

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


def should_receive_strike(participation_data: ClanStrikeInfo, tag: str) -> Tuple[bool, int, int]:
    """Determine whether a user should receive a strike based on their participation in the clan's most recent River Race.

    Args:
        participation_data: Relevant strike determination data for a clan.
        tag: Tag of the user in the clan to determine whether or not they should receive a strike.
    Returns:
        Tuple of whether user should receive a strike, number of medals earned/decks used, and number of medals/decks required.
    """
    def deck_based_participation(days_tracked: int,
                                 deck_usage: List[Union[int, None]],
                                 decks_required: int,
                                 completed_saturday: bool) -> Tuple[bool, int, int]:
        """Determine if a user should receive a strike based on their deck usage.

        Args:
            days_tracked: How many Battle Days the user was in the clan for.
            deck_usage: Number of decks used each Battle Day. Index 0 is first day, index 3 is final day.
            decks_required: Number of decks required to be used each day.
            completed_saturday: Whether the clan crossed the finish line a day early.
        
        Returns:
            Tuple of whether user should receive a strike, how many decks they used, and how many were expected of them."""
        expected_decks = days_tracked * decks_required

        if completed_saturday:
            expected_decks -= decks_required

        index = 2 if completed_saturday else 3
        decks_used = 0

        while days_tracked > 0 and index >= 0:
            if deck_usage[index] is None:
                LOG.warning(f"No deck usage detected at index {index}")
                expected_decks -= decks_required
            else:
                decks_used += deck_usage[index]

            index -= 1
            days_tracked -= 1

        return (decks_used < expected_decks, decks_used, expected_decks)


    def medal_based_participation(days_tracked: int,
                                  medals_earned: int,
                                  medals_required: int,
                                  completed_saturday: bool) -> Tuple[bool, int, int]:
        """Determine if a user should receive a strike based on how many medals they earned.

        Args
            days_tracked: How many Battle Days the user was in the clan for.
            medals_earned: How many medals they earned.
            medals_required: How many medals are required to not get a strike.
            completed_saturday: Whether the clan crossed teh finish line a day early.

        Returns:
            Tuple of whether the user received a strike, how many medals they earned, and how many were expected of them.
        """
        medals_required_per_day = medals_required / 4
        actual_required = medals_required_per_day * days_tracked

        if completed_saturday:
            actual_required -= medals_required_per_day

        return (medals_earned < actual_required, medals_earned, actual_required)


    if tag not in participation_data["users"]:
        LOG.warning(f"Missing user {tag} in clan participation data")
        return (None, None, None)

    reset_times = participation_data["reset_times"]

    # Attempt to correct any missing reset time data by adding/subtracting from adjacent reset times
    if not all(reset_times):
        LOG.warning("Missing daily reset time, attempting to correct")

        if not any(reset_times):
            LOG.error("No daily reset times detected")
            return (None, None, None)
        else:
            for i in range(4):
                if not reset_times[i]:
                    next_index = (i + 1) % 4

                    while(next_index != i):
                        if reset_times[next_index]:
                            diff = i - next_index
                            if diff > 0:
                                reset_times[i] = reset_times[next_index] + datetime.timedelta(days=diff)
                            else:
                                reset_times[i] = reset_times[next_index] - datetime.timedelta(days=-diff)
                        else:
                            next_index = (next_index + 1) % 4

                    if next_index == i:
                        LOG.error("Could not correct missing reset time")
                        return (None, None, None)

    # Determine how many days the user was in the clan after initially joining
    user = participation_data["users"][tag]
    tracked_since = user["tracked_since"]
    days_tracked = 1

    for count, reset_time in enumerate(reset_times):
        if tracked_since <= reset_time:
            days_tracked = 4 - count
            break

    # Determine whether user should receive a strike based on strike type and their participation
    if participation_data["strike_type"] == StrikeType.Decks:
        return deck_based_participation(days_tracked,
                                        user["deck_usage"],
                                        participation_data["strike_threshold"],
                                        participation_data["completed_saturday"])
    elif participation_data["strike_type"] == StrikeType.Medals:
        return medal_based_participation(days_tracked,
                                         user["medals"],
                                         participation_data["strike_threshold"],
                                         participation_data["completed_saturday"])


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
