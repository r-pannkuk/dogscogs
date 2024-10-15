import typing
import uuid
import discord
import datetime

from dogscogs import constants

ScheduleType = typing.Literal["at", "every", "cron"]

def create_schedule(
    *,
    id: typing.Optional[str] = None,
    is_active: bool = True,
    channel_ids: typing.List[typing.Union[int, discord.TextChannel]],
    author_id: typing.Union[int, discord.User, discord.Member],
    type: ScheduleType = "at",
    schedule: 'ScheduleDefinition',
    content: str,
    created_at: float = datetime.datetime.now(tz=constants.TIMEZONE).timestamp(),
    no_runs: int = 0,
    last_run_at: typing.Union[None, float] = None,
) -> "Schedule":
    return {
        "id": id or str(uuid.uuid4().int),
        "is_active": is_active,
        "channel_ids": [c if isinstance(c, int) else c.id for c in channel_ids],
        "author_id": author_id if isinstance(author_id, int) else author_id.id,
        "type": type,
        "schedule": schedule,
        "content": content,
        "no_runs": no_runs,
        "created_at": created_at,
        "last_run_at": last_run_at
    }
class ScheduleDefinition(typing.TypedDict):
    at: typing.Union[None, float]
    interval_secs: typing.Union[None, int]
    cron: typing.Union[None, str]

class Schedule(typing.TypedDict):
    id: str
    is_active: bool
    channel_ids: typing.List[int]
    author_id: int
    type: ScheduleType
    schedule: ScheduleDefinition
    content: str
    no_runs: int
    created_at: float
    last_run_at: typing.Union[None, float]

class GuildConfig(typing.TypedDict):
    schedules: typing.List[Schedule]