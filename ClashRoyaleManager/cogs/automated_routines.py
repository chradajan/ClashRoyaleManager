"""Automated routines cog."""

import datetime
from typing import Dict

import aiocron
import discord
from discord.ext import commands

import utils.clash_utils as clash_utils
import utils.db_utils as db_utils
import utils.discord_utils as discord_utils
import utils.stat_utils as stat_utils
from log.logger import LOG
from utils.channel_manager import CHANNEL
from utils.custom_types import PrimaryClan, ReminderTime, SpecialChannel, StrikeType
from utils.exceptions import GeneralAPIError

class AutomatedRoutines(commands.Cog):
    """Automated routines."""
    GUILD: discord.Guild = None
    PRIMARY_CLANS: Dict[str, PrimaryClan] = {}

    # Reset time check variables
    RESET_OCCURRED: Dict[str, bool] = {}
    LAST_CHECK_SUM: Dict[str, int] = {}
    LAST_DECK_USAGE: Dict[str, Dict[str, int]] = {}

    def __init__(self, guild: discord.Guild):
        """Save bot for access to the guild object."""
        AutomatedRoutines.GUILD = guild

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

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if clan["track_stats"]:
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
            db_utils.clean_up_database()

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if clan["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, False)

            LOG.automation_end()


        @aiocron.crontab('0 0-9 * * 5,6,0,1')
        async def morning_stats_checker():
            """Check Battle Day stats hourly."""
            LOG.automation_start("Starting morning Battle Day stats check")
            db_utils.clean_up_database()

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if clan["track_stats"]:
                    stat_utils.update_clan_battle_day_stats(tag, False)

            LOG.automation_end()


        @aiocron.crontab('0 2 * * 5,6,0,1')
        async def automated_reminder_us():
            """Send a reminder for all clans with reminders enabled. Mention users with a US reminder time preference."""
            LOG.automation_start("Sending US reminders")
            send_embed = False

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if clan["send_reminders"] and not db_utils.is_completed_saturday(tag):
                    LOG.info(f"Sending reminder for {tag}")
                    send_embed = True
                    await discord_utils.send_reminder(tag, ReminderTime.US)

            if send_embed:
                embed = discord.Embed(title="This is an automated reminder",
                                      description=("Any Discord users that have their reminder time preference set to `US` were "
                                                   "pinged. If you were pinged but would like to to be mentioned in the earlier "
                                                   "reminder, use the `/set_reminders` command and choose `EU`."))
                await CHANNEL[SpecialChannel.Reminders].send(embed=embed)

            LOG.automation_end()


        @aiocron.crontab('0 19 * * 4,5,6,0')
        async def automated_reminder_eu():
            """Send a reminder for all clans with reminders enabled. Mention users with an EU reminder time preference."""
            LOG.automation_start("Sending EU reminders")
            send_embed = False

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if clan["send_reminders"] and not db_utils.is_completed_saturday(tag):
                    LOG.info(f"Sending reminder for {tag}")
                    send_embed = True
                    await discord_utils.send_reminder(tag, ReminderTime.EU)

            if send_embed:
                embed = discord.Embed(title="This is an automated reminder",
                                    description=("Any Discord users that have their reminder time preference set to `EU` were "
                                                 "pinged. If you were pinged but would like to to be mentioned in the later "
                                                 "reminder, use the `/set_reminders` command and choose `US`."))
                await CHANNEL[SpecialChannel.Reminders].send(embed=embed)

            LOG.automation_end()


        @aiocron.crontab('30 7,15,23 * * *')
        async def update_all_members():
            """Update all members of the Discord server."""
            LOG.automation_start("Updating all Discord members")
            await discord_utils.update_all_members(AutomatedRoutines.GUILD)
            LOG.automation_end()


        @aiocron.crontab('0 10 * * 0')
        async def check_early_completion_status():
            """Check if each clan has crossed the finish line early."""
            LOG.automation_start("Starting early finish checks")

            for tag in AutomatedRoutines.PRIMARY_CLANS:
                race_info = clash_utils.get_current_river_race_info(tag)
                db_utils.set_completed_saturday(tag, race_info["completed_saturday"])

            LOG.automation_end()


        @aiocron.crontab('0 18 * * 1')
        async def assign_strikes():
            """Assign automated strikes based on performance in most recent River Race."""
            LOG.automation_start("Assigning automated strikes")

            for tag, clan in AutomatedRoutines.PRIMARY_CLANS.items():
                if not clan["assign_strikes"]:
                    continue

                LOG.info(f"Determining strikes for members of {tag}")

                try:
                    active_members = clash_utils.get_active_members_in_clan(tag)
                except GeneralAPIError:
                    LOG.warning(f"Could not get active members of {tag} for determining strikes")
                    continue

                participation_data = db_utils.get_strike_determination_data(tag)
                channel = CHANNEL[SpecialChannel.Strikes]
                message = ""
                mentions = ""

                if participation_data["strike_type"] == StrikeType.Decks:
                    message = (f"**The following members of {discord.utils.escape_markdown(clan['name'])} did not meet the minimum "
                               f"requirement of {participation_data['strike_threshold']} decks used per Battle Day and have "
                               "received a strike:\n**")
                elif participation_data["strike_type"] == StrikeType.Medals:
                    message = (f"**The following members of {discord.utils.escape_markdown(clan['name'])} did not meet the minimum "
                               f"requirement of {participation_data['strike_threshold']} medals and have received a strike:\n")

                embed_one = discord.Embed()
                embed_two = discord.Embed()
                field_count = 0

                for player_tag, user_data in participation_data["users"].items():
                    should_receive_strike, actual, required = stat_utils.should_receive_strike(participation_data, player_tag)

                    if should_receive_strike:
                        if player_tag in active_members:
                            key = user_data["discord_id"] or player_tag
                            previous_strikes, updated_strikes = db_utils.update_strikes(key, 1)

                            if previous_strikes is None:
                                LOG.warning(f"Unable to assign strikes to {player_tag} for clan {tag}")
                                continue

                            if user_data["discord_id"] is not None:
                                member = discord.utils.get(channel.members, id=user_data["discord_id"])

                                if member is not None:
                                    mentions += member.mention + " "

                            if participation_data["strike_type"] == StrikeType.Medals:
                                strike_field = (
                                    f"```Strikes: {previous_strikes} -> {updated_strikes}\n"
                                    f"Medals: {actual}/{int(required)}\n"
                                    f"Date: {user_data['tracked_since'].strftime('%a, %b %d %H:%M UTC')}```"
                                )
                            elif participation_data["strike_type"] == StrikeType.Decks:
                                for i, decks_used in enumerate(user_data["deck_usage"]):
                                    if decks_used is None:
                                        user_data["deck_usage"][i] = '-'

                                strike_field = (
                                    f"```Strikes: {previous_strikes} -> {updated_strikes}\n"
                                    f"Thu: {user_data['deck_usage'][0]}, Fri: {user_data['deck_usage'][1]}, "
                                    f"Sat: {user_data['deck_usage'][2]}, Sun: {user_data['deck_usage'][3]}\n"
                                    f"Date: {user_data['tracked_since'].strftime('%a, %b %d %H:%M UTC')}```"
                                )

                            if field_count < 25:
                                embed_one.add_field(name=user_data["name"], value=strike_field, inline=False)
                            else:
                                embed_two.add_field(name=user_data["name"], value=strike_field, inline=False)

                            field_count += 1
                        else:
                            # TODO: Take note of non-active members that participated but did not meet participation requirements.
                            continue

                message += mentions
                await channel.send(content=message, embed=embed_one)

                if field_count > 25:
                    await channel.send(embed=embed_two)

            LOG.automation_end()
