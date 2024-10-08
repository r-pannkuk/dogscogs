import asyncio
from datetime import datetime, timedelta
import re
from typing import Literal
import typing

import discord
from discord.ext import tasks
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.constants.regex import IP_ADDRESS as REGEX_IP_ADDRESS, PORT as REGEX_PORT

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "output_channel_id": None,
    "cleanup_interval_mins": 120,
}

DEFAULT_MEMBER = {
    "ip": None,
    "port": None,
    "message_text": None,
    "message_id": None,
    "channel_id": None,
    "host_cleanup_fn": None,
}

REGEX_FULL = REGEX_IP_ADDRESS + ":" + REGEX_PORT


class HostCrier(commands.Cog):
    """
    Calls out host messages in a designated channel.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
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
            # embed.timestamp = datetime.now().astimezone(tz=TIMEZONE)
            pass

        return await channel.send(embed=embed)
    
    async def _check_previous(self, host: discord.Member, success, missing_error, channel_error, message_error):
        config = self.config.member(host)
        
        channel_id = await config.channel_id()
        message_id = await config.message_id()
        
        await config.channel_id.set(None)
        await config.message_id.set(None)
        
        if channel_id is None or message_id is None:
            return await missing_error()

        try:
            channel : discord.TextChannel = await self.bot.fetch_channel(channel_id) # type: ignore[assignment]
        except:
            return await channel_error()
        
        if channel:
            try:
                message : discord.Message = await channel.fetch_message(message_id)
            except:
                return await message_error()

        return await success(message)
    
    async def _delete_previous(self, host: discord.Member):
        async def missing_error():
            return 'You don\'t have a recorded host message active, IDIOT!'
        
        async def channel_error():
            return 'The original channel doesn\'t exist anymore.'
        
        async def message_error():
            return 'The host message was already deleted.'

        async def success(message: discord.Message):
            await message.delete()
            return 'Host message removed.'
        
        return await self._check_previous(host, success, missing_error, channel_error, message_error)


    @commands.group()
    async def hostcrier(self, ctx: commands.GuildContext):
        """Command functions for host commands.
        """
        pass

    @hostcrier.command()
    @commands.is_owner()
    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        await super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @hostcrier.command()   
    @commands.is_owner()
    async def red_delete_all(self, ctx: commands.GuildContext) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        await self.config.clear_all()
        await ctx.send('Done')

    @hostcrier.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
        """Provides or sets the output channel for host commands.

        Args:
            ctx (commands.GuildContext): Command Context
            channel (discord.TextChannel): (Optional) The channel to set the outputs to.
        """
        output_channel_id = await self.config.guild(ctx.guild).output_channel_id()

        if channel is None:
            if output_channel_id is not None:
                channel = await self.bot.fetch_channel(output_channel_id) # type: ignore[assignment]

            if output_channel_id is None or channel is None:
                await ctx.send(f"There is no channel set yet, please set one with ``hostcrier channel <channel>``")
                return
        
        await self.config.guild(channel.guild).output_channel_id.set(channel.id)
        
        await ctx.send(f"Echoing hosts into {channel.mention}.")
        pass

    

    @hostcrier.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def interval(self, ctx: commands.GuildContext, mins: typing.Optional[int]):
        """Sets the interval at which messages auto delete in minutes.

        Args:
            ctx (commands.GuildContext): Command Context
            mins (typing.Optional[int]): The number of minutes inbetween checks.
        """
        interval = await self.config.guild(ctx.guild).cleanup_interval_mins()

        if mins is not None:
            if mins < 1:
                await ctx.send(f"That doesn't make any sense, please use your brain and submit a valid interval.")
                return
            
            await self.config.guild(ctx.guild).cleanup_interval_mins.set(mins)
            interval = mins
        elif interval is None:
            await ctx.send(f"Auto-delete interval is not set, please set one using ``hostcrier interval <mins>``")
            return
        
        await ctx.send(f"Auto-deleting host messages after {interval} minute{'s' if interval > 1 else ''}.")
        pass


    @hostcrier.command()
    async def info(self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]):
        """Displays saved info about this user.

        Args:
            ctx (commands.GuildContext): Command Context
            member (typing.Optional[discord.Member]): The user to fetch info for. 
        """
        if member is None:
            member = ctx.author

        await self._output_message(ctx.channel, member, False) # type: ignore[arg-type]

        pass


    @commands.command()
    async def hostgr(self, ctx: commands.GuildContext, full_ip: typing.Optional[str], *, text: typing.Optional[str]):
        """Hosts a game for the given user under their IP with the stated message.

        Args:
            ctx (commands.GuildContext): Command Context
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
        elif len(text) > 100:
            await ctx.reply('Message output is too long; please limit it to 100 characters.')
            return
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

        message = await self._output_message(channel, ctx.author) # type: ignore[arg-type]

        await self.config.member(ctx.author).message_id.set(message.id)
        await self.config.member(ctx.author).channel_id.set(message.channel.id)

        await ctx.reply(message.jump_url)

        @tasks.loop(seconds=30)
        async def host_check():
            cleanup_interval_mins = await self.config.guild(ctx.guild).cleanup_interval_mins()

            offset = (message.created_at + timedelta(minutes=cleanup_interval_mins)).astimezone(tz=pytz.timezone('UTC'))

            if datetime.now().astimezone(tz=pytz.timezone('UTC')) > offset:
                try:
                    if await channel.fetch_message(message.id) is not None:
                        await ctx.send(f"Hey idiot, you're not hosting anymore, are you? {ctx.author.mention}")
                except:
                    pass
                finally:
                    host_check.cancel()
                return            

        host_check.start()
        pass

    @commands.command()
    async def unhost(self, ctx: commands.GuildContext):
        """Removes the previous host message from the user.

        Args:
            ctx (commands.GuildContext): Command context.
        """
        await ctx.reply(await self._delete_previous(ctx.author))

        pass



