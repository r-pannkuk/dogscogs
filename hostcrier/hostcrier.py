from datetime import datetime
import re
from typing import Literal
import typing

import discord
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "output_channel_id": None,
}

DEFAULT_MEMBER = {
    "ip": None,
    "port": None,
    "message_text": None,
    "message_id": None,
    "channel_id": None,
}

REGEX_IP_ADDRESS = "(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
REGEX_PORT = """(?:
      (?![7-9]\\d\\d\\d\\d) #Ignrore anything above 7....
      (?!6[6-9]\\d\\d\\d)  #Ignore anything abovr 69...
      (?!65[6-9]\\d\\d)   #etc...
      (?!655[4-9]\\d)
      (?!6553[6-9])
      (?!0+)            #ignore complete 0(s)
      (?P<Port>\\d{1,5})
    )"""
REGEX_FULL = REGEX_IP_ADDRESS + ":" + REGEX_PORT


class HostCrier(commands.Cog):
    """
    Calls out host messages in a designated channel.
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
        pass

    def _to_ip_address(*args, **kwargs):
        """Validates if a string can be an IP address or not
        """
        if re.match("\b" + REGEX_IP_ADDRESS + "\b", re.X, args[0]):
            return args[0]
        else:
            raise ValueError(f"{args[0]} is not a valid IP address.")
        
    def _to_port(*args, **kwargs):
        """Validates if a string can be a valid port or not
        """
        if re.match("\b" + REGEX_PORT + "\b", re.X, args[0]):
            return args[0]
        else:
            raise ValueError(f"{args[0]} is not a valid port number.")
        
    async def _output_message(self, channel: discord.TextChannel, host: discord.Member, creation_info: typing.Optional[bool] = True) -> discord.Message:
        """Outputs a message to the provided channel.

        Args:
            channel (discord.TextChannel): Destination channel.
            host (discord.Member): The member hosting the game.
            ip (str): The IP of the user.
            port (str): The port of the user.
            text (typing.Optional[str]): An optional message for the game.
        """
        config = self.config.member(host)
        ip = await config.ip()
        port = await config.port()
        text = await config.message_text()

        embed = discord.Embed()

        embed.description = f"**Host**: {host.mention}"
        embed.description += "\n" + f"```\n{ip}:{port}```"

        if text is not None:
            embed.description += f"**Message**: " + text

        if(creation_info):
            embed.set_footer(text=datetime.now().astimezone(tz=pytz.timezone("US/Eastern")).ctime())

        return await channel.send(embed=embed)
    
    async def _delete_previous(self, host: discord.Member):
        config = self.config.member(host)
        
        channel_id = await config.channel_id()
        message_id = await config.message_id()
        
        await config.channel_id.set(None)
        await config.message_id.set(None)
        
        if channel_id is None or message_id is None:
            return 'You don\'t have a recorded host message active, IDIOT!'

        try:
            channel : discord.TextChannel = await self.bot.fetch_channel(channel_id)
        except:
            return 'The original channel doesn\'t exist anymore.'
        
        if channel:
            try:
                message : discord.Message = await channel.fetch_message(message_id)
                await message.delete()
            except:
                return 'The host message was already deleted.'

        return 'Host message removed.'


    @commands.group()
    async def hostcrier(self, ctx: commands.Context):
        """Command functions for host commands.
        """
        pass

    @hostcrier.command()
    @commands.is_owner()
    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @hostcrier.command()   
    @commands.is_owner()
    async def red_delete_all(self, ctx: commands.Context) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        await self.config.clear_all()
        await ctx.send('Done')

    @hostcrier.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def channel(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel]):
        """Provides or sets the output channel for host commands.

        Args:
            ctx (commands.Context): Command Context
            channel (discord.TextChannel): (Optional) The channel to set the outputs to.
        """
        output_channel_id = await self.config.guild(ctx.guild).output_channel_id()

        if channel is not None:
            await self.config.guild(channel.guild).output_channel_id.set(channel.id)
        else:
            if output_channel_id is not None:
                channel = await self.bot.fetch_channel(output_channel_id)
            else:
                await ctx.send(f"There is no channel set yet, please set one with ``hostcrier channel <channel>``")
                return
        
        await ctx.send(f"Echoing hosts into {channel.mention}.")
        pass


    @hostcrier.command()
    async def info(self, ctx: commands.Context, member: typing.Optional[discord.Member]):
        """Displays saved info about this user.

        Args:
            ctx (commands.Context): Command Context
            member (typing.Optional[discord.Member]): The user to fetch info for. 
        """
        if member is None:
            member = ctx.author

        await self._output_message(ctx.channel, member, False)

        pass


    @commands.command()
    async def hostgr(self, ctx: commands.Context, full_ip: typing.Optional[str], *, text: typing.Optional[str]):
        """Hosts a game for the given user under their IP with the stated message.

        Args:
            ctx (commands.Context): Command Context
            full_ip (typing.Optional[str]): The user's IP (filled in if known): <###.###.###.###:#####>
            text (typing.Optional[str]): Any message associated with this game.
        """

        help_msg = "please provide your IP and Port in the format: <###.###.###.###:#####>"

        if full_ip is None:
            ip = await self.config.member(ctx.author).ip()
            port = await self.config.member(ctx.author).port()

            if port is None or ip is None:
                await ctx.reply(f"Could not find IP information, {help_msg}")
                return
        else:
            match = re.search(f"\\b{REGEX_FULL}\\b", full_ip, re.X)

            if match:
                parts = match.group(0).split(":")
                ip = parts[0]
                port = parts[1]

                await self.config.member(ctx.author).ip.set(ip)
                await self.config.member(ctx.author).port.set(port)
            else:
                await ctx.reply(f"IP information provided was invalid, {help_msg}")
                return
        
        if text is None:
            text = await self.config.member(ctx.author).message_text()
        else:
            await self.config.member(ctx.author).message_text.set(text)

        channel_id = await self.config.guild(ctx.guild).output_channel_id()
        
        if channel_id is None:
            await ctx.reply('No output channel is set, please ask a mod to set a channel.')
            return
        
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except:
            await ctx.reply('Channel was not found, please contact a mod for help.')
            return
        
        await self._delete_previous(ctx.author)

        message = await self._output_message(channel, ctx.author)

        await self.config.member(ctx.author).message_id.set(message.id)
        await self.config.member(ctx.author).channel_id.set(message.channel.id)

        await ctx.reply(message.jump_url)

        pass

    @commands.command()
    async def unhost(self, ctx: commands.Context):
        """Removes the previous host message from the user.

        Args:
            ctx (commands.Context): Command context.
        """
        await ctx.reply(await self._delete_previous(ctx.author))

        pass



