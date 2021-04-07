from typing import Literal

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

BASECOG = getattr(commands, "Cog", object)
DEF_GUILD = {
    "dump_channel": None
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
        self.config.register_guild(**DEF_GUILD)


    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
        return


    @commands.guild_only()
    @commands.is_owner()
    @commands.command(usage="<channel>")
    async def set_dump_channel(self, ctx, channel: discord.TextChannel):
        """
        Sets the channel where communications will be sent.
        """
        await self.config.guild(ctx.guild).dump_channel.set(channel.id)
        await ctx.send("Done. Set {} as the channel for communications.".format(channel.mention))
        
        return
        

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listens for private messages to forward to the dump channel.
        """
        if not message.channel.type == discord.ChannelType.private:
            return
        
        if message.content.startswith(self.config.guild(ctx.guild).get_prefix(message)):
            return

        message.reply("Yes, I did it!")
        return