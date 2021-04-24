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


class ChannelPM(commands.Cog):
    """
    Messages to the bot will be redirected to a specified channel.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=331669086813814784,
            force_registration=True,
        )
        self.config.register_global(**DEF_GLOBAL)


    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
        return
    

    @commands.group()
    async def channelpm(self, ctx):
        """
        Manages channel PM's.
        """
        pass


    @commands.guild_only()
    @commands.is_owner()
    @channelpm.command(usage="<channel>")
    async def channel(self, ctx, channel: Optional[discord.TextChannel]):
        """
        Sets the channel where communications will be sent.
        """
        if channel is None:
            channel = self.bot.get_channel(await self.config.dump_channel())

            if channel is None:
                return await ctx.send("PM channel currently not set.")

            return await ctx.send("PM channel currently set to {}.".format(channel.mention))

        await self.config.dump_channel.set(channel.id)
        await ctx.send("Done. Set {} as the channel for communications.".format(channel.mention))        
        return
    
    @commands.guild_only()
    @commands.mod()
    @commands.command(usage="<user> <message>", rest_is_raw=True)
    async def pm(self, ctx, user: discord.User, *, message: str):
        """
        Mesages a user indirectly via the bot.
        """
        if ctx.author == self.bot.user:
            return

        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return
        
        response_channel = self.bot.get_channel(await self.config.dump_channel())

        if response_channel is None:
            await self.config.dump_channel.set(ctx.channel.id)

        response = """**{0}>{1}#{2}**: {3}""".format(ctx.author.display_name, user.name, user.discriminator, message)

        await user.send(response)
        await ctx.channel.send(response)
        await ctx.message.delete()

        return

    @commands.guild_only()
    @commands.mod()
    @commands.command(usage="<message>", rest_is_raw=True)
    async def r(self, ctx, *, message: str):
        """
        Replies to the last person who messaged the bot.
        """
        await self.pm(ctx, self.bot.get_user(await self.config.reply_target()), message=message)
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

        channel = self.bot.get_channel(await self.config.dump_channel())

        if channel is None:
            return

        await self.config.reply_target.set(message.author.id)

        private_message = """**{0}#{1}**: {2}""".format(message.author.name, message.author.discriminator, message.content)
        await channel.send(private_message)
        return