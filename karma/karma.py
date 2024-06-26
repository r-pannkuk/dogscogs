import datetime
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from .embeds import KarmaEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "valid_stickers": {
        1226341561495851030 : 1,
        1254952247343972393 : 0,
        1254608441234821171 : -1,
    },
    "after_timestamp": 1719147600
}

DEFAULT_MEMBER = {
    "stickers_found": {},
}

class Karma(commands.Cog):
    """
    Karma for using stickers.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)
        self.config.register_member(**DEFAULT_MEMBER)

    async def _count_stickers(self, message: discord.Message) -> None:        
        valid_sticker_ids = await self.config.guild(message.guild).valid_stickers()
        message_sticker_ids = [sticker.id for sticker in message.stickers]

        stickers_found : typing.Dict[str, typing.List[int]]= await self.config.member(message.author).stickers_found()
        write = False

        for sticker_id in message_sticker_ids:
            if str(sticker_id) in valid_sticker_ids.keys():
                if str(sticker_id) not in stickers_found:
                    stickers_found[str(sticker_id)] = []
                    write = True

                if message.id not in stickers_found[str(sticker_id)]:
                    stickers_found[str(sticker_id)].append(int(message.id))
                    write = True

        if write:
            await self.config.member(message.author).stickers_found.set(stickers_found)

    @commands.command()
    @commands.guild_only()
    async def karma(self, ctx: commands.Context, *, user: typing.Optional[discord.Member]) -> None:
        """Displays the karma for the user.

        Args:
            user (typing.Optional[discord.Member]): An optional user to look up.
        """

        if user is None:
            user = ctx.author

        stickers_found : typing.Dict[str, typing.List[int]]= await self.config.member(user).stickers_found()
        valid_stickers = await self.config.guild(ctx.guild).valid_stickers()

        karma = 0
        count = 0

        for sticker_id, message_ids in stickers_found.items():
            karma += valid_stickers[sticker_id] * len(message_ids)
            count += len(message_ids)

        if count > 0:
            karma = float(karma) / count

        if karma >= 0.75:
            rating = "Lawful Good"
        elif karma >= 0.25:
            rating = "Good"
        elif karma <= -0.75:
            rating = "Chaotic Evil"
        elif karma <= -0.25:
            rating = "Evil"
        else:
            rating = "Neutral"

        embed = KarmaEmbed(ctx, user=user, sticker_counts=stickers_found, karma=karma, rating=rating)
        await ctx.send(embed=embed)

        pass

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def count_karma(self, ctx: commands.Context) -> None:
        after_timestamp = await self.config.guild(ctx.guild).after_timestamp()
        after = datetime.datetime.fromtimestamp(after_timestamp)
        for channel in ctx.guild.text_channels:
            try:
                async for message in channel.history(limit=None, after=after):
                    if not hasattr(message.author, 'guild'):
                        continue
                    await self._count_stickers(message)
            except discord.Forbidden:
                continue

        await ctx.send("Karma counted.")

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        await self._count_stickers(message)
