"""Automated routines cog."""

import datetime
from typing import Dict

import aiocron
from discord.ext import commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
import utils.stat_utils as stat_utils
from log.logger import LOG
from utils.custom_types import PrimaryClan, ReminderTime
from utils.exceptions import GeneralAPIError

class AutomatedRoutines(commands.Cog):
    """Automated routines."""
    BOT: commands.Bot = None
    PRIMARY_CLANS: Dict[str, PrimaryClan] = {}

    # Reset time check variables
    RESET_OCCURRED: Dict[str, bool] = {}
    LAST_CHECK_SUM: Dict[str, int] = {}
    LAST_DECK_USAGE: Dict[str, Dict[str, int]] = {}

    def __init__(self, bot: commands.Bot):
        """Save bot for access to the guild object."""
        AutomatedRoutines.BOT = bot

        for clan in db_utils.get_primary_clans():
            AutomatedRoutines.PRIMARY_CLANS[clan["tag"]] = clan
            AutomatedRoutines.RESET_OCCURRED[clan["tag"]] = False
            AutomatedRoutines.LAST_CHECK_SUM[clan["tag"]] = -1
            AutomatedRoutines.LAST_DECK_USAGE[clan["tag"]] = {}


        @aiocron.crontab('20-58 9 * * *')
        async def reset_time_check():
            """Check for the daily reset."""
            tags = [tag for tag, reset_occurred in AutomatedRoutines.RESET_OCCURRED.items() if not reset_occurred]

            if not tags:
                return

            LOG.automation_start("Checking reset time")
            weekday = datetime.datetime.utcnow().weekday()

            for tag in tags:
                try:
                    deck_usage = clash_utils.get_deck_usage_today(tag)
                except GeneralAPIError:
                    LOG.warning(f"Skipping reset time check for {tag}")
                    continue

                usage_sum = sum(deck_usage.values())

                if usage_sum < AutomatedRoutines.LAST_CHECK_SUM[tag]:
                    LOG.info(f"Daily reset detected for clan {tag}")

                    try:
                        db_utils.clean_up_database()
                    except GeneralAPIError:
                        LOG.warning("Error occurred while cleaning up database")
                        AutomatedRoutines.LAST_CHECK_SUM[tag] = 201
                        continue

                    AutomatedRoutines.RESET_OCCURRED[tag] = True

                    if weekday == 3:
                        db_utils.prepare_for_battle_days(tag)
                    elif weekday in {4, 5, 6} and AutomatedRoutines.PRIMARY_CLANS[tag]["track_stats"]:
                        stat_utils.update_clan_battle_day_stats(tag, False)
                        stat_utils.save_river_race_clans_info(tag, False)

                    db_utils.record_deck_usage_today(tag, weekday, AutomatedRoutines.LAST_DECK_USAGE[tag])
                else:
                    AutomatedRoutines.LAST_CHECK_SUM[tag] = usage_sum
                    AutomatedRoutines.LAST_DECK_USAGE[tag] = deck_usage

            LOG.automation_end()


        @aiocron.crontab('59 9 * * *')
        async def final_reset_time_check():
            """Perform daily reset routine if not already performed and reset tracking variables."""
            LOG.automation_start("Final reset time check")

            tags = [tag for tag, reset_occurred in AutomatedRoutines.RESET_OCCURRED.items() if not reset_occurred]

            if tags:
                weekday = datetime.datetime.utcnow().weekday()

                try:
                    db_utils.clean_up_database()
                except GeneralAPIError:
                    LOG.warning("Error occurred while cleaning up database")

            for tag in tags:
                LOG.warning(f"Daily reset not detected for clan {tag}")

                try:
                    deck_usage = clash_utils.get_deck_usage_today(tag)
                except GeneralAPIError:
                    LOG.warning(f"Skipping final reset time check for {tag}")
                    continue

                usage_sum = sum(deck_usage.values())

                if usage_sum > AutomatedRoutines.LAST_CHECK_SUM[tag]:
                    deck_usage = AutomatedRoutines.LAST_DECK_USAGE[tag]

                if weekday == 3:
                    db_utils.prepare_for_battle_days(tag)
                elif weekday in {4, 5, 6} and AutomatedRoutines.PRIMARY_CLANS[tag]["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, False)
                    stat_utils.save_river_race_clans_info(tag, False)

                db_utils.record_deck_usage_today(tag, weekday, deck_usage)

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                AutomatedRoutines.RESET_OCCURRED[tag] = False
                AutomatedRoutines.LAST_CHECK_SUM[tag] = -1
                AutomatedRoutines.LAST_DECK_USAGE[tag] = {}

            LOG.automation_end()


        @aiocron.crontab('0 10 * * 1')
        async def end_of_race_check():
            """Perform final stats checks after River Race and create new River Race entries."""
            LOG.automation_start("Starting end of race checks")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                if AutomatedRoutines.PRIMARY_CLANS[tag]["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, True)
                    stat_utils.save_river_race_clans_info(tag, True)

            if clash_utils.is_first_day_of_season():
                db_utils.create_new_season()

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                db_utils.prepare_for_river_race(tag)

            LOG.automation_end()


        @aiocron.crontab('0 10-23 * * 4,5,6,0')
        async def evening_stats_checker():
            """Check Battle Day stats hourly."""
            LOG.automation_start("Starting evening Battle Day stats check")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                if AutomatedRoutines.PRIMARY_CLANS[tag]["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, False)

            LOG.automation_end()


        @aiocron.crontab('0 0-9 * * 5,6,0,1')
        async def morning_stats_checker():
            """Check Battle Day stats hourly."""
            LOG.automation_start("Starting morning Battle Day stats check")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                if AutomatedRoutines.PRIMARY_CLANS[tag]["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, False)

            LOG.automation_end()


        @aiocron.crontab('0 2 * * 5,6,0,1')
        async def automated_reminder_us():
            """Send a reminder for all clans with reminders enabled. Mention users with a US reminder time preference."""
            LOG.automation_start("Sending US reminders")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                if AutomatedRoutines.PRIMARY_CLANS[tag]["send_reminders"]:
                    LOG.info(f"Sending reminder for {tag}")
                    await discord_utils.send_reminder(tag, ReminderTime.US, True)

            LOG.automation_end()


        @aiocron.crontab('0 19 * * 4,5,6,0')
        async def automated_reminder_eu():
            """Send a reminder for all clans with reminders enabled. Mention users with an EU reminder time preference."""
            LOG.automation_start("Sending EU reminders")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                if AutomatedRoutines.PRIMARY_CLANS[tag]["send_reminders"]:
                    LOG.info(f"Sending reminder for {tag}")
                    await discord_utils.send_reminder(tag, ReminderTime.EU, True)

            LOG.automation_end()
