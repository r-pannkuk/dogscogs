import typing
import discord
from croniter import croniter # type: ignore[import-untyped]
from redbot.core.config import Config

from .config import Schedule

class ScheduledSayEmbed(discord.Embed):
    def __init__(self, config: Config, guild: discord.Guild, schedule_id: str):
        self.config = config
        self.guild = guild
        self.schedule_id = schedule_id

        super().__init__(title="Generating...", description="...")

    async def send(self) -> "ScheduledSayEmbed":
        schedules : typing.List[Schedule] = await self.config.guild(self.guild).schedules()
        schedule = next((s for s in schedules if s['id'] == self.schedule_id), None)

        if schedule is None:
            raise ValueError(f"No schedule found for the given id: {self.schedule_id}")
        
        self.title = f"Schedule: {schedule['id']}"

        channels = [self.guild.get_channel(id) or await self.guild.fetch_channel(id) for id in schedule['channel_ids']]
        author = self.guild.get_member(schedule['author_id']) or await self.guild.fetch_member(schedule['author_id'])

        self.description = ""

        self.description += f"__Active__: {'Yes' if schedule['is_active'] else 'No'}\n"
        self.description += f"__Author__: {author.mention}\n"
        self.description += f"__Channels__: {', '.join([c.mention for c in channels])}\n"
        self.description += f"__Type__: `{schedule['type'].capitalize()}`\n"

        if schedule['type'] == "at":
            self.description += f"__At__: <t:{int(schedule['schedule']['at'])}:F>\n" # type: ignore[arg-type]

        elif schedule['type'] == "every":
            self.description += f"__At__: <t:{int(schedule['schedule']['at'])}:F>\n" # type: ignore[arg-type]
            self.description += f"__Interval__: Every {schedule['schedule']['interval_secs']} seconds\n"

        elif schedule['type'] == "cron":
            cron = croniter(schedule['schedule']['cron'])
            self.description += f"__Cron__: {schedule['schedule']['cron']}\n"
            self.description += f"__Next__: <t:{int(cron.get_next())}:F>\n" # type: ignore[arg-type]
            
        self.description += f"__Created At__: <t:{int(schedule['created_at'])}>\n"
        
        last_run_at = f"<t:{int(schedule['last_run_at'])}>" if schedule['last_run_at'] is not None else ''
        
        self.description += f"__Last Run At__: {last_run_at}\n"
        self.description += f"__Number of Runs__: {schedule['no_runs']}\n\n"
        
        self.add_field(name="", value=schedule['content'])

        return self