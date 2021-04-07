from typing import Literal, Optional

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

BASECOG = getattr(commands, "Cog", object)
DEF_GLOBAL = {
    "dump_channel": None,
    "reply_target": None
}

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class ChannelDM(commands.Cog):
    """
    Messages to the bot will be redirected to a specified channel.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier="Klypto#3347",
            force_registration=True,
        )
        self.config.register_global(**DEF_GLOBAL)


    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
        return


    @commands.guild_only()
    @commands.is_owner()
    @commands.command(usage="<channel>")
    async def channel(self, ctx, channel: Optional[discord.TextChannel]):
        """
        Sets the channel where communications will be sent.
        """
        if channel is None:
            await self.config.GLOBAL.dump_channel.set(None)
            return await ctx.send("Done. Cleared DM channel.")

        await self.config.GLOBAL.dump_channel.set(channel)
        await ctx.send("Done. Set {} as the channel for communications.".format(channel.mention))
        
        return
    
    @commands.guild_only()
    @commands.mod()
    @commands.command(usage="<user> <message>")
    async def pm(self, ctx, user: discord.User, message: str):
        if ctx.author == self.bot.user:
            return

        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return
        
        response_channel = await self.config.GLOBAL.dump_channel()

        if response_channel is None:
            self.config.GLOBAL.dump_channel.set(ctx.channel)

        response = """**{0}>{1}**: {2}""".format(ctx.author.display_name(), user.display_name(), message)

        await user.send(response)
        await ctx.channel.send(response)
        await ctx.message.delete()

        return

    @commands.guild_only()
    @commands.mod()
    @commands.command(usage="<message>")
    async def r(self, ctx, message: discord.Message):
        await self.pm(ctx, self.config.GLOBAL.reply_target(), message)
        return
        

    @commands.dm_only()
    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listens for private messages to forward to the dump channel.
        """
        if not message.channel.type == discord.ChannelType.private:
            return

        if message.author == self.bot.user:
            return

        if message.content.startswith(tuple(await self.bot.get_valid_prefixes())) is True:
            return

        channel = self.config.GLOBAL.dump_channel()

        if channel is None:
            return

        await self.config.GLOBAL.reply_target.set(message.author)

        await channel.send("""**{0}**: {1}""".format(message.author.mention, message.content))
        return