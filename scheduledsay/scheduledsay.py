import datetime
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger # type: ignore[import-untyped]
from apscheduler.triggers.date import DateTrigger # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger # type: ignore[import-untyped]

from dogscogs.constants import TIMEZONE

from .config import GuildConfig, Schedule
from .views import ScheduledSayListPaginatedEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD : GuildConfig = {
    "schedules": [],
}

scheduler = AsyncIOScheduler(timezone="US/Eastern")

async def schedule_message(config: Config, guild: discord.Guild, schedule_id: str) -> None:
    schedules : typing.List[Schedule] = await config.guild(guild).schedules()
    schedule = next((s for s in schedules if s['id'] == schedule_id), None)

    if schedule is None:
        raise ValueError("No schedule found for the given id.")

    if scheduler.get_job(schedule['id']) is not None:
        scheduler.remove_job(schedule['id'])

    if schedule['is_active']:        
        if schedule['type'] == "at":
            trigger = DateTrigger(run_date=datetime.datetime.fromtimestamp(float(schedule['schedule']['at']))) # type: ignore[arg-type]
        elif schedule['type'] == "every":
            trigger = IntervalTrigger(
                start_date=datetime.datetime.fromtimestamp(float(schedule['schedule']['at'])), # type: ignore[arg-type]
                seconds=schedule['schedule']['interval_secs'], timezone=TIMEZONE # type: ignore[arg-type]
            )
        elif schedule['type'] == "cron":
            trigger = CronTrigger.from_crontab(schedule['schedule']['cron'], timezone=TIMEZONE)

        scheduler.add_job(
            run_scheduled_message, 
            trigger,
            id=schedule['id'],
            args=[config, guild, schedule['id']]
        )

async def run_scheduled_message(config: Config, guild: discord.Guild, schedule_id: str) -> None:
    if guild is None:
        return

    schedules : typing.List[Schedule] = await config.guild(guild).schedules()
    i, schedule = next((i, s) for i, s in enumerate(schedules) if s['id'] == schedule_id)

    if schedule is None:
        raise ValueError("No schedule found for the given id.")

    if schedule['is_active'] is False:
        return

    for id in schedule['channel_ids']:
        try:
            channel = guild.get_channel(id) or await guild.fetch_channel(id)
        except discord.NotFound:
            author = guild.get_member(schedule['author_id'])
            if author is not None:
                await author.send(f"Channel `{id}` not found for schedule `{schedule_id}`.")
            continue

        await channel.send(schedule['content']) # type: ignore[union-attr]
        schedule['no_runs'] += 1
        schedule['last_run_at'] = datetime.datetime.now(tz=TIMEZONE).timestamp()

    schedules[i] = schedule # type: ignore[index]
    await config.guild(guild).schedules.set(schedules)

    pass

class ScheduledSay(commands.Cog):
    """
    Schedules the bot to say something somewhere.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

        scheduler.start()

    async def cog_load(self) -> None:
        guild_configs : typing.Dict[int, GuildConfig] = await self.config.all_guilds()

        for id, guild_config in guild_configs.items():
            guild = await self.bot.fetch_guild(id)
            if guild is None:
                continue

            schedules : typing.List[Schedule] = guild_config['schedules']
            for schedule in schedules:
                await schedule_message(self.config, guild, schedule['id'])
                pass
        pass

    @commands.group()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def ssay(self, ctx: commands.Context):
        """Manage scheduled messages."""
        pass

    @ssay.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def list(self, ctx: commands.Context):
        """List scheduled messages."""
        await ScheduledSayListPaginatedEmbed(
            bot=self.bot,
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
            filter=lambda m: m['author_id'] == ctx.author.id
        ).send()
        pass