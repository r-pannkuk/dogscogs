from datetime import datetime
import re
from typing import Literal
import typing

import discord
from discord.ext.commands.errors import PrivateMessageOnly
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "enabled": True,
    "output_channel_id": None,
    "input_channel_id": None,
    "use_rich_embeds": True,
    "use_pings": True
}

DEFAULT_MEMBER = {
    "ip": None,
    "port": None,
    "created_date": None,
    "last_modified_date": None,
    "message_id": None,
    "channel_id": None
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

class ipcrier(commands.Cog):
    """
    Echoes any IP's found into a designated channel.
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
    
    async def _post_to_output_channel_embed(self, player1: discord.Member, player2: typing.Optional[discord.Member]):
        """Posts the output channel message as a rich embed.

        Args:
            player1 (discord.Member): The player who instigated the IP call.
            player2 (typing.Optioinal[discord.Member]): The opponent (fetched from mentions).
        """
        output_channel_id = await self.config.guild(player1.guild).output_channel_id()
        output_channel = await self.bot.fetch_channel(output_channel_id)

        config = self.config.member(player1)
        ip = await config.ip()
        port = await config.port()

        embed = discord.Embed()

        embed.description = f"**Host**: {player1.mention}"
        content = None

        if player2 != None:
            if await self.config.guild(player1.guild).use_pings():
                content = player2.mention
            embed.description += "\n" + f"Opponent: {player2.mention}"
        else:
            embed.description += "\n"

        embed.description += "\n" + f"```fix\n{ip}:{port}\n```"

        embed.set_footer(text=datetime.now().astimezone(tz=pytz.timezone("US/Eastern")))

        await output_channel.send(content=content, embed=embed)
        pass

    async def _post_to_output_channel_simple(self, player1: discord.Member, player2: typing.Optional[discord.Member]):
        """Posts the output channel message as a simple text message.

        Args:
            player1 (discord.Member): The player who instigated the IP call.
            player2 (typing.Optioinal[discord.Member]): The opponent (fetched from mentions).
        """
        output_channel_id = await self.config.guild(player1.guild).output_channel_id()
        output_channel = await self.bot.fetch_channel(output_channel_id)

        config = self.config.member(player1)
        ip = await config.ip()
        port = await config.port()

        timestamp = datetime.now().astimezone(tz=pytz.timezone('US/Eastern'))
        message = f"[{timestamp.strftime('%H:%M:%S')}] "

        if await self.config.guild(player1.guild).use_pings():
            message += f"**{player1.mention}**"
            
            if player2 != None:
                message += f" (Host) vs. {player2.mention}"
        else:
            message += f"**{player1.display_name}**"

            if player2 != None:
                message += f" vs. {player2.display_name}"

        message += "\n" + f"```fix\n{ip}:{port}\n```"

        await output_channel.send(message)
        pass

    async def _post_to_output_channel(self, player1: discord.Member, player2: typing.Optional[discord.Member]):
        """Posts a user's IP address and port to an outpout channel.

        Args:
            player1 (discord.Member): The player instigating the match.
            player2 (typing.Optional[discord.Member]): The other player who is in the match.
        """
        if await self.config.guild(player1.guild).use_rich_embeds():
            await self._post_to_output_channel_embed(player1, player2)
        else: 
            await self._post_to_output_channel_simple(player1, player2)
        pass

    async def _set(self, member: discord.Member, ip: _to_ip_address, port: _to_port):
        """Sets an IP pairing for the specific user.

        Args:
            member (discord.Member): The user who owns this IP address.
            ip (to_ip_address): The IP address string.
            port (to_port): The port number.
        """
        config = self.config.member(member)

        await config.ip.set(ip)
        await config.port.set(port)
        await config.created_date.set(await config.created_date() or datetime.now().timestamp())
        await config.last_modified_date.set(datetime.now().timestamp())
        pass

    def _clear(self):
        pass

    async def _set_output_channel(self, channel: discord.TextChannel):
        """Designates a current output channel for the server.

        Args:
            channel (discord.TextChannel): The channel being set to.
        """
        await self.config.guild(channel.guild).output_channel_id.set(channel.id)
        pass

    async def _set_input_channel(self, channel: discord.TextChannel):
        """Designates a current input channel for the server.

        Args:
            channel (discord.TextChannel): The channel being set to.
        """
        await self.config.guild(channel.guild).input_channel_id.set(channel.id)
        pass

    @commands.group()
    async def ipcrier(self, ctx: commands.Context):
        """Configs any settings used by the cog.

        Args:
            ctx (commands.Context): [description]
        """
        pass

    @ipcrier.command()
    @commands.mod_or_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Sets whether or not the cog is currently enabled.

        Args:
            ctx (commands.Context): The command context.
            bool (typing.Optional[bool]): Whether or not the cog is enabled.
        """
        if bool != None:
            await self.config.guild(ctx.guild).enabled.set(bool)
            if bool:
                output_string = f"IP Crier is now `ENABLED`."
            else:
                output_string = f"IP Crier is now `DISABLED`."
        else:
            bool = await self.config.guild(ctx.guild).enabled()
            output_channel_id = await self.config.guild(ctx.guild).output_channel_id()
            input_channel_id = await self.config.guild(ctx.guild).input_channel_id()
            
            
            if bool:
                output_string = f"IP Crier is currently `ENABLED`.\n"
                prefix = await ctx.bot.get_prefix(ctx.message)

                if isinstance(prefix, list):
                    prefix = prefix[0]

                if input_channel_id != None:
                    input_channel = await self.bot.fetch_channel(input_channel_id)
                    output_string += f"Currently reading IP's from {input_channel.mention}.\n"
                else:
                    output_string += f"ERROR: No Input Channel has been set; please use `{prefix}ipcrier set-input-channel #channel`.\n"

                if output_channel_id != None:
                    output_channel = await self.bot.fetch_channel(output_channel_id)
                    output_string += f"Currently echoing IP's into {output_channel.mention}.\n"
                else:
                    output_string += f"ERROR: No Output Channel has been set; please use `{prefix}ipcrier set-output-channel #channel`.\n"
            else:
                output_string = f"IP Crier is currently `DISABLED`."
        
        await ctx.send(output_string)
        pass

    @ipcrier.command(name="set-output-channel")
    @commands.mod_or_permissions(manage_roles=True)
    async def set_output_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Sets the output channel to echo IP's into.

        Args:
            ctx (commands.Context): The command context.
            channel (discord.TextChannel): The target channel.
        """
        # if not await self.config.guild(ctx.guild).enabled():
        #     await ctx.send(f"IP Crier is currently DISABLED.")

        input_channel_id = await self.config.guild(ctx.guild).input_channel_id()

        if input_channel_id == channel.id:
            input_channel = await self.bot.fetch_channel(input_channel_id)
            await ctx.send(f"ERROR: Cannot set input channel {input_channel.mention} as the output channel.")
            return

        await self._set_output_channel(channel)
        
        await ctx.send(f"Now echoing IP's into {channel.mention}.")

    @ipcrier.command(name="set-input-channel")
    @commands.mod_or_permissions(manage_roles=True)
    async def set_input_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Sets the input channel to read IP's from.

        Args:
            ctx (commands.Context): The command context.
            channel (discord.TextChannel): The target channel.
        """
        # if not await self.config.guild(ctx.guild).enabled():
        #     await ctx.send(f"IP Crier is currently DISABLED.")

        output_channel_id = await self.config.guild(ctx.guild).output_channel_id()

        if output_channel_id == channel.id:
            output_channel = await self.bot.fetch_channel(output_channel_id)
            await ctx.send(f"ERROR: Cannot set output channel {output_channel.mention} as the input channel.")
            return

        await self._set_input_channel(channel)
        
        await ctx.send(f"Now reading IP's from {channel.mention}.")

    @ipcrier.command(name="use-pings")
    @commands.mod_or_permissions(manage_roles=True)
    async def use_pings(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Sets whether or not to ping users in the echoed channel.

        Args:
            ctx (commands.Context): The command context.
            bool (typing.Optional[bool]): Whether or not to ping.
        """
        if bool != None:
            await self.config.guild(ctx.guild).use_pings.set(bool)
        else:
            bool = await self.config.guild(ctx.guild).use_pings()
        
        
        if bool:
            output_string = f"User pinging is currently `ENABLED`."
        else:
            output_string = f"User pinging is currently `DISABLED`."
        
        await ctx.send(output_string)
        pass

    @ipcrier.command(name="use-rich-embeds")
    @commands.mod_or_permissions(manage_roles=True)
    async def use_rich_embeds(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Sets whether or not to use rich embed messages for IP crier.

        Args:
            ctx (commands.Context): The command context.
            bool (typing.Optional[bool]): Whether or not to use rich embeds.
        """
        if bool != None:
            await self.config.guild(ctx.guild).use_rich_embeds.set(bool)
        else:
            bool = await self.config.guild(ctx.guild).use_rich_embeds()
        
        
        if bool:
            output_string = f"`Rich Embeds` are currently being used for IP callouts."
        else:
            output_string = f"`Simple Text` is currently being used for IP callouts."
        
        await ctx.send(output_string)
        pass

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for IP posts to echo them.

        Args:
            message (discord.Message): Message to scan.
        """
        if (
            message.guild == None or
            not await self.config.guild(message.guild).enabled() or 
            await self.config.guild(message.guild).input_channel_id() != message.channel.id or
            await self.config.guild(message.guild).output_channel_id() == None
        ) :
            return
        
        match = re.search(f"\\b{REGEX_FULL}\\b", message.content, re.X)

        if match:
            parts = match.group(0).split(":")
            ip = parts[0]
            port = parts[1]
            
            await self._set(message.author, ip, port)

            if len(message.mentions) > 0:
                await self._post_to_output_channel(message.author, message.mentions[0])
            else:
                await self._post_to_output_channel(message.author, None)


        pass