from typing import Literal

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class ChannelDM(commands.Cog):
    """
    Messages to the bot will be redirected to a specified channel.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=Klypto#3347,
            force_registration=True,
        )

    @commands.command()
    async def very_specific_test_command(self, ctx):
        await ctx.send("I can do stuff.")
        

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
