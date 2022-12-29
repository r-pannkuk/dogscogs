from typing import Literal

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class test(commands.Cog):
    """
    A short description of the cog.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context):
        await ctx.send(content="Hello")
        pass