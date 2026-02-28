import discord
from discord.ext import commands
import logging
import traceback
import sys
from datetime import datetime

class ErrorLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.logger = logging.getLogger("discord_error_logger")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        sys.excepthook = self.handle_uncaught_exception

        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        error_trace = traceback.format_exc()

        self.logger.info(
            "\n"
            "================ COMMAND ERROR ================\n"
            f"Time: {datetime.utcnow()}\n"
            f"User: {ctx.author} (ID: {ctx.author.id})\n"
            f"Guild: {ctx.guild} (ID: {ctx.guild.id if ctx.guild else 'DM'})\n"
            f"Channel: {ctx.channel} (ID: {ctx.channel.id})\n"
            f"Command: {ctx.command}\n"
            f"Message Content: {ctx.message.content}\n"
            f"Error: {repr(error)}\n"
            f"Traceback:\n{error_trace}"
            "================================================\n"
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        error_trace = traceback.format_exc()

        self.logger.info(
            "\n"
            "================ SLASH ERROR ==================\n"
            f"Time: {datetime.utcnow()}\n"
            f"User: {interaction.user} (ID: {interaction.user.id})\n"
            f"Guild: {interaction.guild} (ID: {interaction.guild.id if interaction.guild else 'DM'})\n"
            f"Channel: {interaction.channel} (ID: {interaction.channel.id if interaction.channel else 'Unknown'})\n"
            f"Command: {interaction.command}\n"
            f"Error: {repr(error)}\n"
            f"Traceback:\n{error_trace}"
            "================================================\n"
        )
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        error_trace = traceback.format_exc()

        self.logger.info(
            "\n"
            "================ EVENT ERROR ==================\n"
            f"Time: {datetime.utcnow()}\n"
            f"Event: {event}\n"
            f"Args: {args}\n"
            f"Kwargs: {kwargs}\n"
            f"Traceback:\n{error_trace}"
            "================================================\n"
        )

    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        self.logger.info(
            "\n"
            "============= UNCAUGHT EXCEPTION ==============\n"
            f"Time: {datetime.utcnow()}\n"
            f"Exception Type: {exc_type}\n"
            f"Exception Value: {exc_value}\n"
            f"Traceback:\n{''.join(traceback.format_tb(exc_traceback))}"
            "================================================\n"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorLogger(bot))