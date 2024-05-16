import json
from pathlib import Path

from redbot.core.bot import Red

from .trigger import Trigger

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot: Red) -> None:
    trigger = Trigger(bot)
    await bot.add_cog(trigger)
    await trigger.load_cogs()