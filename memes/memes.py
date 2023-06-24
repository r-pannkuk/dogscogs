from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "channels": [],
    "roles": [],
}

class Memes(commands.Cog):
    """
    Meme container for custom dumb commands.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)


    @commands.group(name="roleroulette")
    async def role_roulette(self, ctx):
        """Assigns roles randomly to users who post in a channel, based on chance.
        """
        pass

    @commands.mod_or_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Sets whether or not the roulette is enabled.

        Args:
            bool (typing.Optional[bool]): Override to true or false.
        """
        guild : discord.Guild = ctx.guild