import datetime
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from apscheduler.job import Job # type: ignore[import-untyped]
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

class ScheduledSay(commands.Cog):
    """
    Schedules the bot to say something somewhere.
    """
    SCHEDULER : AsyncIOScheduler = None

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

        if not hasattr(self.bot, 'ssay_scheduler'):
            setattr(self.bot, 'ssay_scheduler', AsyncIOScheduler(timezone="US/Eastern"))
            getattr(self.bot, 'ssay_scheduler').start()

        ScheduledSay.SCHEDULER = getattr(self.bot, 'ssay_scheduler')

    @staticmethod
    async def schedule_message(config: Config, guild: discord.Guild, schedule_id: str) -> None:
        schedules : typing.List[Schedule] = await config.guild(guild).schedules()
        schedule = next((s for s in schedules if s['id'] == schedule_id), None)

        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        if ScheduledSay.SCHEDULER.get_job(schedule['id']) is not None:
            ScheduledSay.SCHEDULER.remove_job(schedule['id'])

        if schedule['is_active']:        
            if schedule['type'] == "at":
                trigger = DateTrigger(run_date=datetime.datetime.fromtimestamp(float(schedule['schedule']['at']))) # type: ignore[arg-type]
            elif schedule['type'] == "every":
                trigger = IntervalTrigger(
                    start_date=datetime.datetime.fromtimestamp(float(schedule['schedule']['at'])), # type: ignore[arg-type]
                    seconds=schedule['schedule']['interval_secs'], timezone=TIMEZONE # type: ignore[arg-type]
                )
            elif schedule['type'] == "cron":
                day_index_map = {
                    "0": "Sun",
                    "1": "Mon",
                    "2": "Tue",
                    "3": "Wed",
                    "4": "Thu",
                    "5": "Fri",
                    "6": "Sat",
                }

                split = schedule['schedule']['cron'].split(' ') # type: ignore[union-attr]
                
                if len(split) == 5 and split[4] in day_index_map.keys():
                    split[4] = day_index_map[split[4]]

                trigger = CronTrigger.from_crontab(' '.join(split), timezone=TIMEZONE)

            ScheduledSay.SCHEDULER.add_job(
                ScheduledSay.run_scheduled_message, 
                trigger,
                id=schedule['id'],
                args=[config, guild, schedule['id']],
                replace_existing=True
            )

    @staticmethod
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

    async def cog_load(self) -> None:
        guild_configs : typing.Dict[int, GuildConfig] = await self.config.all_guilds()

        ScheduledSay.SCHEDULER.remove_all_jobs()

        for id, guild_config in guild_configs.items():
            guild = await self.bot.fetch_guild(id)
            if guild is None:
                continue

            schedules : typing.List[Schedule] = guild_config['schedules']
            for schedule in schedules:
                await ScheduledSay.schedule_message(self.config, guild, schedule['id'])
                pass
        pass

    @commands.group()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def ssay(self, ctx: commands.Context):
        """Manage scheduled messages."""
        pass

    @ssay.command()
    @commands.is_owner()
    async def jobs(self, ctx: commands.Context):
        """List scheduled jobs."""
        jobs : typing.List[Job] = ScheduledSay.SCHEDULER.get_jobs()

        description = ""

        for job in jobs:
            next_run_time : datetime.datetime = job.next_run_time

            description += f"\tID: {job.id}"

            if next_run_time is not None:
                description += f" @ <t:{int(next_run_time.timestamp())}>"

            description += "\n"
        await ctx.send(f"Jobs:\n{description}")
        pass

    @ssay.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def list(self, ctx: commands.Context, *, query: typing.Optional[str] = None):
        """List scheduled messages."""
        if query is not None and query.lower() == 'all':
            filter = lambda m: True
        else:
            filter = lambda m: m['author_id'] == ctx.author.id

        await ScheduledSayListPaginatedEmbed(
            bot=self.bot,
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
            filter=filter
        ).send()
        pass