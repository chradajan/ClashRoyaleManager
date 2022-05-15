"""Logging tools."""

import json
import logging
import logging.config
import os

import discord

def log_message(msg: str="", **kwargs) -> str:
    """Format a message with arguments for the log.

    Args:
        msg: Message to be displayed in log.
        kwargs: Any key word arguments passed in will be displayed on their own line in the log as "    key: value".

    Returns:
        Message with arguments formatted for the log.
    """
    args_str = '\n'

    for key, value in kwargs.items():
        if all(hasattr(value, attr) for attr in ['discriminator', 'name', 'display_name']):
            value = f"{value.display_name} - {value.name}#{value.discriminator}"

        args_str += f"{' ' * 4}{key}: {value}" + '\n'

    args_str = args_str[:-1]
    return msg + args_str

# Define custom logging levels to identify the start and end of commands and automated routines.
automation_start_name = "AUTOMATION_START"
automation_start_num = logging.DEBUG + 1

automation_end_name = "AUTOMATION_END"
automation_end_num = logging.DEBUG + 2

command_start_name = "COMMAND_START"
command_start_num = logging.DEBUG + 3

command_end_name = "COMMAND_END"
command_end_num = logging.DEBUG + 4

# Define custom functions in logger associated with the levels defined above.
def automation_start_log(self, msg: str, *args, **kwargs):
    """Definition of LOG.automation_start()

    Args:
        msg: Message to include with log entry. Used for name of automated routine.
        args: Unused.
        kwargs: Unused.
    """
    if self.isEnabledFor(automation_start_num):
        self._log(automation_start_num, msg, args, **kwargs)

def automation_end_log(self, msg: str="", *args, **kwargs):
    """Definition of LOG.automation_end()

    Args:
        msg: Message to include with log entry. Either leave blank or provide reason for automated routine to return early.
        args: Unused.
        kwargs: Unused.
    """
    if self.isEnabledFor(automation_end_num):
        self._log(automation_end_num, msg, args, **kwargs)

def command_start_log(self, command: discord.Interaction, *args, **kwargs):
    """Definition of LOG.command_start()

    Args:
        ctx: Used to log the command name, initiator, and channel.
        args: Unused.
        kwargs: Provide any other keyword arguments such as command parameters to log.
    """
    if self.isEnabledFor(command_start_num):
        msg = log_message(Command=command.command.name,
                          Initiator=f"{command.user.display_name} - {command.user},",
                          Channel=command.channel,
                          **kwargs)
        self._log(command_start_num, msg, args, {})

def command_end_log(self, msg: str="", *args, **kwargs):
    """Definition of LOG.automation_end()

    Args:
        msg: Message to include with log entry. Either leave blank or provide reason for command to return early.
        args: Unused.
        kwargs: Unused.
    """
    if self.isEnabledFor(command_end_num):
        self._log(command_end_num, msg, args, **kwargs)

# Add custom attributes to logger class.
logging.addLevelName(automation_start_num, automation_start_name)
logging.addLevelName(automation_end_num, automation_end_name)
logging.addLevelName(command_start_num, command_start_name)
logging.addLevelName(command_end_num, command_end_name)

setattr(logging, automation_start_name, automation_start_num)
setattr(logging, automation_end_name, automation_end_num)
setattr(logging, command_start_name, command_start_num)
setattr(logging, command_end_name, command_end_num)

setattr(logging.getLoggerClass(), automation_start_name.lower(), automation_start_log)
setattr(logging.getLoggerClass(), automation_end_name.lower(), automation_end_log)
setattr(logging.getLoggerClass(), command_start_name.lower(), command_start_log)
setattr(logging.getLoggerClass(), command_end_name.lower(), command_end_log)

# Create directory for log files if it doesn't exist.
if not os.path.exists('log/logs'):
    os.makedirs('log/logs')

# Get logging configuration settings and create global LOG object.
with open("log/logging_config.json") as logging_config_file:
    logging_config = json.load(logging_config_file)
    logging.config.dictConfig(logging_config)
    LOG = logging.getLogger("main_logger")
