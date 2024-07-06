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
        1258093939076890726 : 1,
        1254952247343972393 : 0,
        1258094007460954123 : -1,
    },
    "after_timestamp": 1719990000
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
        if message.type != discord.MessageType.reply:
            return
            
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
    @commands.cooldown(1, 60 * 60 * 24 * 14, lambda ctx: ctx.author.id if not ctx.author.guild_permissions.manage_roles else datetime.datetime.now().timestamp())
    async def karma(self, ctx: commands.Context, *, user: discord.Member) -> None:
        """Displays the karma for the user.y

        Args:
            user (typing.Optional[discord.Member]): An optional user to look up.
        """
        if user == ctx.author and not ctx.author.guild_permissions.manage_roles:
            await ctx.reply("It's pretty cringe to care about your own Karma so much.")
            return


        stickers_found : typing.Dict[str, typing.List[int]]= await self.config.member(user).stickers_found()
        valid_stickers = await self.config.guild(ctx.guild).valid_stickers()

        karma = 0.0
        count = 0
        
        sticker_count = {str(sticker_id): 0 for sticker_id in valid_stickers.keys()}

        for sticker_id, message_ids in stickers_found.items():
            karma += valid_stickers[sticker_id] * len(message_ids)
            count += len(message_ids)
            sticker_count[str(sticker_id)] += len(message_ids)

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

        embed = KarmaEmbed(
            ctx, 
            title=f"{user.display_name}'s Karma", 
            sticker_counts=sticker_count if ctx.author.guild_permissions.manage_roles else {}, 
            karma=karma, 
            rating=rating
        )
        await ctx.send(embed=embed)

        pass

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def reset_karma(self, ctx: commands.Context) -> None:
        await self.config.clear_all_members(ctx.guild)
        await ctx.send("Karma reset.")
            

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

    @commands.command(aliases=["serverkarma", "karma_server", "karmaserver", "karmaall", "karma_all", "totalkarma", "total_karma"])
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def server_karma(self, ctx: commands.Context) -> None:
        members = await self.config.all_members(ctx.guild)
        valid_stickers = await self.config.guild(ctx.guild).valid_stickers()

        karma = 0.0
        count = 0

        sticker_counts = {str(sticker_id): 0 for sticker_id in valid_stickers.keys()}

        for i in members:
            stickers_found : typing.Dict[str, typing.List[int]]= members[i]['stickers_found']

            for sticker_id, message_ids in stickers_found.items():
                karma += valid_stickers[sticker_id] * len(message_ids)
                count += len(message_ids)

                sticker_counts[str(sticker_id)] += len(message_ids)

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

        embed = KarmaEmbed(ctx, title=f"Total {ctx.guild} Karma", sticker_counts=sticker_counts, karma=karma, rating=rating)
        await ctx.send(embed=embed)

    @commands.command(aliases=["top_karma", "karmastats", "karma_stats"])
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def topkarma(self, ctx: commands.Context) -> None:
        members = await self.config.all_members(ctx.guild)
        valid_stickers = await self.config.guild(ctx.guild).valid_stickers()

        count : typing.Dict[str, typing.Dict[str, int]]= {}

        for i in members:
            stickers_found : typing.Dict[str, typing.List[int]]= members[i]['stickers_found']
            count[i] = {str(i): 0 for i in valid_stickers.keys()}

            for sticker_id, message_ids in stickers_found.items():
                count[i][sticker_id] += len(message_ids)

        embed = discord.Embed(title=f"Most Frequent Karma Manipulators")

        for i in valid_stickers.keys():
            sticker : discord.Sticker = next((sticker for sticker in ctx.guild.stickers if sticker.id == int(i)), None)
            if sticker == None:
                continue

            desc = ""

            sorted_count = sorted(count.items(), key=lambda x: x[1][i], reverse=True)

            place = 1

            for j in sorted_count[:10]:
                user = ctx.guild.get_member(j[0])
                desc += f"{place}) {user.mention}: {j[1][i]}\n"
                place += 1

            embed.add_field(name=f"`{sticker.name}` Usage", value=desc, inline=False)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        await self._count_stickers(message)
