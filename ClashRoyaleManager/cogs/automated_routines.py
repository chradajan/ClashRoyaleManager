"""Automated routines cog."""

import datetime
from typing import Dict, Tuple

import aiocron
import discord
from discord.ext import commands

from utils import clash_utils
from utils import db_utils
from utils import discord_utils
from utils import stat_utils
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.custom_types import ReminderTime, SpecialChannel
from utils.exceptions import GeneralAPIError
from utils.outside_battles_queue import UNSENT_WARNINGS

async def drain_outside_battle_warnings():
    """Send a warning message for each member who's joined after using battles in another clan."""
    primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

    for (clash_data, outside_battles) in UNSENT_WARNINGS:
        if primary_clans[clash_data["clan_tag"]]["assign_strikes"]:
            await discord_utils.send_outside_battles_warning(clash_data, outside_battles)

    UNSENT_WARNINGS.clear()

class AutomatedRoutines(commands.Cog):
    """Automated routines."""
    GUILD: discord.Guild = None

    # Reset time check variables
    RESET_OCCURRED: Dict[str, bool] = {}
    LAST_CHECK_SUM: Dict[str, int] = {}
    LAST_DECK_USAGE: Dict[str, Dict[str, Tuple[int, int]]] = {}
    POST_RESET_USAGE: Dict[str, Dict[str, Tuple[int, int]]] = {}

    def __init__(self, guild: discord.Guild):
        """Save bot for access to the guild object."""
        AutomatedRoutines.GUILD = guild

        for clan in db_utils.get_primary_clans():
            AutomatedRoutines.RESET_OCCURRED[clan["tag"]] = False
            AutomatedRoutines.LAST_CHECK_SUM[clan["tag"]] = -1
            AutomatedRoutines.LAST_DECK_USAGE[clan["tag"]] = {}
            AutomatedRoutines.POST_RESET_USAGE[clan["tag"]] = {}


        @aiocron.crontab('20-58 9 * * *')
        async def reset_time_check():
            """Check for the daily reset."""
            try:
                tags = [tag for tag, reset_occurred in AutomatedRoutines.RESET_OCCURRED.items() if not reset_occurred]

                if not tags:
                    return

                LOG.automation_start("Checking reset time")
                weekday = datetime.datetime.utcnow().weekday()
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}
                api_is_broken = db_utils.update_cards_in_database()

                for tag in tags:
                    try:
                        deck_usage = clash_utils.get_deck_usage_today(tag, False)
                    except GeneralAPIError:
                        LOG.warning(f"Skipping reset time check for {tag}")
                        continue

                    usage_sum = sum([decks_used_today for decks_used_today, _ in deck_usage.values()])

                    if usage_sum < AutomatedRoutines.LAST_CHECK_SUM[tag]:
                        LOG.info(f"Daily reset detected for clan {tag}")

                        AutomatedRoutines.POST_RESET_USAGE[tag] = deck_usage

                        try:
                            db_utils.clean_up_database()
                        except GeneralAPIError:
                            LOG.warning("Error occurred while cleaning up database")
                            AutomatedRoutines.LAST_CHECK_SUM[tag] = 201
                            continue

                        AutomatedRoutines.RESET_OCCURRED[tag] = True

                        if weekday == 3:
                            db_utils.prepare_for_battle_days(tag)
                        elif weekday in {4, 5, 6} and primary_clans[tag]["track_stats"]:
                            stat_utils.update_clan_battle_day_stats(tag, False, api_is_broken)
                            stat_utils.save_river_race_clans_info(tag, False)

                        db_utils.record_deck_usage_today(tag, weekday, AutomatedRoutines.LAST_DECK_USAGE[tag])
                    else:
                        AutomatedRoutines.LAST_CHECK_SUM[tag] = usage_sum
                        AutomatedRoutines.LAST_DECK_USAGE[tag] = deck_usage

                LOG.automation_end()
            except Exception as e:
                LOG.exception(e)


        @aiocron.crontab('59 9 * * *')
        async def final_reset_time_check():
            """Perform daily reset routine if not already performed and reset tracking variables."""
            primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

            try:
                LOG.automation_start("Final reset time check")

                tags = [tag for tag, reset_occurred in AutomatedRoutines.RESET_OCCURRED.items() if not reset_occurred]
                api_is_broken = db_utils.update_cards_in_database()

                if tags:
                    weekday = datetime.datetime.utcnow().weekday()

                    try:
                        db_utils.clean_up_database()
                    except GeneralAPIError:
                        LOG.warning("Error occurred while cleaning up database")

                for tag in tags:
                    LOG.warning(f"Daily reset not detected for clan {tag}")

                    try:
                        deck_usage = clash_utils.get_deck_usage_today(tag, False)
                    except GeneralAPIError:
                        LOG.warning(f"Skipping final reset time check for {tag}")
                        db_utils.set_clan_reset_time(tag, weekday)
                        continue

                    usage_sum = sum([decks_used_today for decks_used_today, _ in deck_usage.values()])

                    if usage_sum < AutomatedRoutines.LAST_CHECK_SUM[tag]:
                        deck_usage = AutomatedRoutines.LAST_DECK_USAGE[tag]

                    AutomatedRoutines.POST_RESET_USAGE[tag] = deck_usage

                    if weekday == 3:
                        db_utils.prepare_for_battle_days(tag)
                    elif weekday in {4, 5, 6} and primary_clans[tag]["track_stats"]:
                        stat_utils.update_clan_battle_day_stats(tag, False, api_is_broken)
                        stat_utils.save_river_race_clans_info(tag, False)

                    db_utils.record_deck_usage_today(tag, weekday, deck_usage)

            except Exception as e:
                LOG.exception(e)

            LOG.automation_end()


        @aiocron.crontab('0 10 * * 0,2-6')
        async def end_of_day():
            LOG.automation_start("Performing end of day routine")
            primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}
            weekday = datetime.datetime.utcnow().weekday()

            for tag in primary_clans:
                db_utils.remedy_deck_usage(tag,
                                           weekday,
                                           AutomatedRoutines.LAST_DECK_USAGE[tag],
                                           AutomatedRoutines.POST_RESET_USAGE[tag])

                AutomatedRoutines.RESET_OCCURRED[tag] = False
                AutomatedRoutines.LAST_CHECK_SUM[tag] = -1
                AutomatedRoutines.LAST_DECK_USAGE[tag] = {}
                AutomatedRoutines.POST_RESET_USAGE[tag] = {}

            LOG.automation_end()


        @aiocron.crontab('0 10 * * 1')
        async def end_of_race_check():
            """Perform final stats checks after River Race and create new River Race entries."""
            LOG.automation_start("Starting end of race checks")
            primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}
            weekday = datetime.datetime.utcnow().weekday()

            for tag in primary_clans:
                try:
                    db_utils.remedy_deck_usage(tag,
                                               weekday,
                                               AutomatedRoutines.LAST_DECK_USAGE[tag],
                                               clash_utils.get_deck_usage_today(tag, True))
                except Exception as e:
                    LOG.exception(e)

                AutomatedRoutines.RESET_OCCURRED[tag] = False
                AutomatedRoutines.LAST_CHECK_SUM[tag] = -1
                AutomatedRoutines.LAST_DECK_USAGE[tag] = {}
                AutomatedRoutines.POST_RESET_USAGE[tag] = {}

            try:
                api_is_broken = db_utils.update_cards_in_database()

                for tag, clan in primary_clans.items():
                    if clan["track_stats"]:
                        stat_utils.update_clan_battle_day_stats(tag, True, api_is_broken)
                        stat_utils.save_river_race_clans_info(tag, True)

            except Exception as e:
                LOG.exception(e)

            if clash_utils.is_first_day_of_season():
                db_utils.create_new_season()

            for tag in primary_clans:
                db_utils.prepare_for_river_race(tag)

            for tag in primary_clans:
                db_utils.fix_anomalies(tag)

            LOG.automation_end()


        @aiocron.crontab('0,15,30,45 10-23 * * 4,5,6,0')
        async def evening_stats_checker():
            """Check Battle Day stats hourly."""
            try:
                LOG.automation_start("Starting evening Battle Day stats check")
                db_utils.clean_up_database()
                api_is_broken = db_utils.update_cards_in_database()
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag, clan in primary_clans.items():
                    if clan["track_stats"]:
                        stat_utils.update_clan_battle_day_stats(tag, False, api_is_broken)

            except Exception as e:
                LOG.exception(e)

            await drain_outside_battle_warnings()
            LOG.automation_end()


        @aiocron.crontab('0,15,30,45 0-9 * * 5,6,0,1')
        async def morning_stats_checker():
            """Check Battle Day stats hourly."""
            try:
                LOG.automation_start("Starting morning Battle Day stats check")
                db_utils.clean_up_database()
                api_is_broken = db_utils.update_cards_in_database()
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag, clan in primary_clans.items():
                    if clan["track_stats"]:
                        stat_utils.update_clan_battle_day_stats(tag, False, api_is_broken)

            except Exception as e:
                LOG.exception(e)

            await drain_outside_battle_warnings()
            LOG.automation_end()


        @aiocron.crontab('30 13 * * 4,5,6,0')
        async def automated_reminder_asia():
            """Send a reminder for all clans with reminders enabled. Mention users with an ASIA reminder time preference."""
            try:
                LOG.automation_start("Sending ASIA reminders")
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag, clan in primary_clans.items():
                    if clan["send_reminders"] and not db_utils.is_completed_saturday(tag):
                        LOG.info(f"Sending reminder for {tag}")
                        channel = AutomatedRoutines.GUILD.get_channel(clan["discord_channel_id"])
                        await discord_utils.send_reminder(tag, channel, ReminderTime.ASIA, True)

                LOG.automation_end()
            except Exception as e:
                LOG.exception(e)


        @aiocron.crontab('0 19 * * 4,5,6,0')
        async def automated_reminder_eu():
            """Send a reminder for all clans with reminders enabled. Mention users with an EU reminder time preference."""
            try:
                LOG.automation_start("Sending EU reminders")
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag, clan in primary_clans.items():
                    if clan["send_reminders"] and not db_utils.is_completed_saturday(tag):
                        LOG.info(f"Sending reminder for {tag}")
                        channel = AutomatedRoutines.GUILD.get_channel(clan["discord_channel_id"])
                        await discord_utils.send_reminder(tag, channel, ReminderTime.EU, True)

                LOG.automation_end()
            except Exception as e:
                LOG.exception(e)


        @aiocron.crontab('0 3 * * 5,6,0,1')
        async def automated_reminder_na():
            """Send a reminder for all clans with reminders enabled. Mention users with a NA reminder time preference."""
            try:
                LOG.automation_start("Sending NA reminders")
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag, clan in primary_clans.items():
                    if clan["send_reminders"] and not db_utils.is_completed_saturday(tag):
                        LOG.info(f"Sending reminder for {tag}")
                        channel = AutomatedRoutines.GUILD.get_channel(clan["discord_channel_id"])
                        await discord_utils.send_reminder(tag, channel, ReminderTime.NA, True)

                LOG.automation_end()
            except Exception as e:
                LOG.exception(e)


        @aiocron.crontab('30 7,15,23 * * *')
        async def update_all_members():
            """Update all members of the Discord server."""
            try:
                LOG.automation_start("Updating all Discord members")
                await discord_utils.update_all_members(AutomatedRoutines.GUILD)
            except Exception as e:
                LOG.exception(e)

            await drain_outside_battle_warnings()
            LOG.automation_end()


        @aiocron.crontab('0 10 * * 0')
        async def check_early_completion_status():
            """Check if each clan has crossed the finish line early."""
            try:
                LOG.automation_start("Starting early finish checks")
                primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

                for tag in primary_clans:
                    race_info = clash_utils.get_current_river_race_info(tag)
                    db_utils.set_completed_saturday(tag, race_info["completed_saturday"])

                LOG.automation_end()
            except Exception as e:
                LOG.exception(e)


        @aiocron.crontab('0 14 * * 1')
        async def assign_strikes():
            """Assign automated strikes based on performance in most recent River Race."""
            LOG.automation_start("Assigning automated strikes")
            primary_clans = {clan["tag"]: clan for clan in db_utils.get_primary_clans()}

            for tag, clan in primary_clans.items():
                try:
                    if not clan["assign_strikes"]:
                        continue

                    LOG.info(f"Determining strikes for members of {tag}")

                    try:
                        active_members = clash_utils.get_active_members_in_clan(tag)
                    except Exception as e:
                        LOG.exception(e)
                        continue

                    clan_strike_data = db_utils.get_clan_strike_determination_data(tag)

                    if not clan_strike_data:
                        LOG.warning("Could not get clan strike data, continuing to next clan")
                        continue

                    strikes_to_give = stat_utils.determine_strikes(clan_strike_data)

                    active_message = (f"**The following members of {discord.utils.escape_markdown(clan['name'])} did not meet the "
                                      f"minimum requirement of {clan_strike_data['strike_threshold']} decks used per Battle Day "
                                      "and have received a strike:\n**")

                    inactive_message = (f"*These users would have received a strike but are not currently in the clan:*\n")

                    active_embeds = [discord.Embed(), discord.Embed()]
                    active_field_count = 0

                    inactive_embeds = [discord.Embed(), discord.Embed()]
                    inactive_field_count = 0

                    for user_strike_data in strikes_to_give:
                        player_name = user_strike_data["name"]
                        player_tag = user_strike_data["tag"]
                        tracked_since = user_strike_data["tracked_since"]
                        deck_usage = user_strike_data["deck_usage"]

                        for i, decks_used in enumerate(deck_usage):
                            if decks_used is None:
                                deck_usage[i] = '-'

                        if player_tag in active_members:
                            previous_strikes, updated_strikes = db_utils.update_strikes(player_tag, 1)

                            if previous_strikes is None:
                                LOG.warning(f"Unable to assign strikes to {player_tag} for clan {tag}")
                                continue

                            field_value = (
                                f"```Strikes: {previous_strikes} -> {updated_strikes}\n"
                                f"Thu: {deck_usage[0]}, Fri: {deck_usage[1]}, "
                                f"Sat: {deck_usage[2]}, Sun: {deck_usage[3]}\n"
                                f"Date: {tracked_since.strftime('%a, %b %d %H:%M UTC')}```"
                            )

                            active_embeds[0 if active_field_count < 25 else 1].add_field(
                                name=discord.utils.escape_markdown(player_name),
                                value=field_value,
                                inline=False
                            )

                            active_field_count += 1
                        else:
                            field_value = (
                                "```"
                                f"Thu: {deck_usage[0]}, Fri: {deck_usage[1]}, "
                                f"Sat: {deck_usage[2]}, Sun: {deck_usage[3]}\n"
                                f"Date: {tracked_since.strftime('%a, %b %d %H:%M UTC')}```"
                            )

                            inactive_embeds[0 if inactive_field_count < 25 else 1].add_field(
                                name=discord.utils.escape_markdown(player_name),
                                value=field_value,
                                inline=False
                            )

                            inactive_field_count += 1

                    if active_field_count == 0:
                        active_message = None
                        active_embeds[0] = discord.Embed(title=("All active members of "
                                                                f"{discord.utils.escape_markdown(clan['name'])} met the minimum "
                                                                "participation requirements. No strikes have been assigned."),
                                                  color=discord.Color.green())

                    await CHANNEL[SpecialChannel.Strikes].send(content=active_message, embed=active_embeds[0])

                    if active_field_count > 25:
                        await CHANNEL[SpecialChannel.Strikes].send(embed=active_embeds[1])

                    if inactive_field_count == 0:
                        inactive_message = None
                        inactive_embeds[0] = discord.Embed(title=(f"All inactive members of "
                                                                  f"{discord.utils.escape_markdown(clan['name'])} that participated "
                                                                  "in the most recent River Race met the minimum participation "
                                                                  "requirements."),
                                                  color=discord.Color.green())

                    await CHANNEL[SpecialChannel.Strikes].send(content=inactive_message, embed=inactive_embeds[0])

                    if inactive_field_count > 25:
                        await CHANNEL[SpecialChannel.Strikes].send(embed=inactive_embeds[1])
                except Exception as e:
                    LOG.exception(e)
                    continue

            LOG.automation_end()
