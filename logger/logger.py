from typing import Literal
import typing

import discord
from discord.permissions import PermissionOverwrite
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

COG_IDENTIFIER = 260288776360820736

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "is_links_enabled": True,
    "logger_channel_id": None,
    "logger_channel_name": "logs",
    "formatted_inline": True
}

FORMAT_ADDED = '`'
FORMAT_REMOVED = '~~'


class LogPayload:
    def __init__(self, event: typing.Union[discord.RawMessageUpdateEvent, discord.RawMessageDeleteEvent]) -> None:
        self._type = None
        if isinstance(event, discord.RawMessageUpdateEvent):
            self._type = 'UPDATE'
            self._before = event.cached_message
            self._message = event.data
        elif isinstance(event, discord.RawMessageDeleteEvent):
            self._type = 'DELETE'
            self._before = event.cached_message
            self._message = None
        self._guild_id = event.guild_id
        self._channel_id = event.channel_id

        return

    @property
    def type(self) -> str:
        """
        What type of event this is.
        """
        return self._type

    @property
    def guild_id(self) -> str:
        """
        The guild ID that this message was from.
        """
        return self._guild_id

    @property
    def channel_id(self) -> str:
        """
        The channel ID that this message was from.
        """
        return self._channel_id

    @property
    def before(self) -> discord.Message:
        """
        The message prior to the event.
        """
        return self._before

    @property
    def data(self) -> typing.Union[dict, discord.Message]:
        """
        The message after the event occurred.
        """
        return self._message

    @property
    def delta_inline(self) -> str:
        """
        The formatted output to print out for logging.
        """
        import difflib
        expected = self.before.content
        actual = self.data['content']
        str = ""
        prev = "  "
        for ele in difflib.Differ().compare(expected, actual):
            comparator = ele[:2]

            if comparator == '  ':
                if prev == '+ ':
                    str += FORMAT_ADDED
                str += f"{ele[2:]}"
            elif comparator == '- ':
                if prev == '+ ':
                    str += FORMAT_ADDED
                str += f"{FORMAT_REMOVED}{ele[2:]}{FORMAT_REMOVED}"
            elif comparator == '+ ':
                if prev == '  ' or prev == '- ':
                    str += FORMAT_ADDED
                str += f"{ele[2:]}"

            prev = comparator

        if prev == '+ ':
            str += FORMAT_ADDED
        return str


class Logger(commands.Cog):
    """
    Logs message deletions and edits.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

        pass

    @commands.group()
    @commands.mod_or_permissions(manage_roles=True)
    async def logger(self, ctx):
        """
        Handles logging for message deletions and edits in the server.
        """
        pass

    @logger.command(usage="<True|False>")
    @commands.mod_or_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """
        Sets whether or not logging is eanbled for deleted / edited messages.
        """
        guild: discord.Guild = ctx.guild
        is_enabled = await self.config.guild_from_id(guild.id).is_enabled()

        logger_channel_id = await self.config.guild_from_id(guild.id).logger_channel_id() 
        prefix = await ctx.bot.get_prefix(ctx.message)

        if isinstance(prefix, list):
            prefix = prefix[0]

        channel_unset_message = f'Please set a logging channel using `{prefix}logger channel <channel>` or create one with `{prefix}logger create <name>`.'
        
        if logger_channel_id is not None:
            logger_channel = guild.get_channel(logger_channel_id)
            channel_set_message = f"Logs will be displayed in {logger_channel.mention}."

        if bool == None:
            status = "**ENABLED**" if is_enabled else "**DISABLED**"
            if is_enabled:
                if logger_channel_id == None:
                    status += f".  {channel_unset_message}"
                else:
                    status += f".  {channel_set_message}"
            await ctx.channel.send(f"Logging of message edits and deletions is currently {status}")
            return

        await self.config.guild_from_id(guild.id).is_enabled.set(bool)

        if bool:
            str = f"Now logging message edits and deletions."
            logger_channel_id = await self.config.guild_from_id(guild.id).logger_channel_id()

            if logger_channel_id == None:
                str += f" {channel_unset_message}"
            else:
                str += f"  {channel_set_message}"

            await ctx.channel.send(str)
        else:
            await ctx.channel.send(f"No longer logging message edits and deletions.")
        return

    @logger.command()
    @commands.mod_or_permissions(manage_roles=True)
    async def enable(self, ctx: commands.Context):
        """
        Enables logging for this bot.
        """
        await self.enabled(ctx, True)
        return

    @logger.command()
    @commands.mod_or_permissions(manage_roles=True)
    async def disable(self, ctx: commands.Context):
        """
        Disables logging for this bot.
        """
        await self.enabled(ctx, False)
        return

    @logger.command(name="links", usage="<True|False>")
    @commands.mod_or_permissions(manage_roles=True)
    async def links_enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """
        Sets whether or not links to original messages will appear in logs.
        """
        guild: discord.Guild = ctx.guild
        is_links_enabled = await self.config.guild_from_id(guild.id).is_links_enabled()

        if bool == None:
            status = "**ENABLED**" if is_links_enabled else "**DISABLED**"
            await ctx.channel.send(f"Links in log messages are currently {status}")
            return

        await self.config.guild_from_id(guild.id).is_links_enabled.set(bool)

        if bool:
            await ctx.channel.send(f"Now displaying links in edit and deletion logs.")
        else:
            await ctx.channel.send(f"No longer displaying links in edit and deletion logs.")
        return

    @logger.command(usage="<channel>")
    @commands.mod_or_permissions(manage_roles=True)
    async def channel(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel]):
        """
        Sets the logger channel to a specified channel on the server. If no channel is provided, it will display what channel is currently set.
        """

        guild: discord.Guild = ctx.guild
        logger_channel_id: str = await self.config.guild_from_id(guild.id).logger_channel_id()
        logger_channel: discord.TextChannel = None

        if logger_channel_id is not None:
            logger_channel = guild.get_channel(logger_channel_id)

        if channel == None:

            if logger_channel == None:
                await ctx.channel.send(f'Logger channel currently not set. Please specify a channel name.')
            else:
                await ctx.channel.send(f'Logger channel currently set to {logger_channel.mention}.')

            return

        if logger_channel and logger_channel.id == channel.id:
            await ctx.channel.send(f'Logger channel is already set to {channel.mention}.')
            return

        await self.config.guild_from_id(guild.id).logger_channel_id.set(channel.id)

        await ctx.channel.send(f'Logger channel now set to {channel.mention}.')
        return

    @logger.command(usage="<name>")
    @commands.mod_or_permissions(manage_roles=True)
    async def create(self, ctx: commands.Context, name: typing.Optional[str]):
        """
        Creates a new logger channel to store message edits and deletions in.
        """
        guild: discord.Guild = ctx.guild

        if name == None:
            name = await self.config.guild_from_id(guild.id).logger_channel_name()

        channels: typing.List[discord.Guild] = [
            channel for channel in guild.channels if channel.name == name]

        if len(channels) > 0:
            await ctx.channel.send(f"Already found existing channel with name {channels[0].mention}. Please use a different name.")
            return

        channel = await guild.create_text_channel(name=name, overwrites={
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
                send_messages=False,
                view_channel=False
            )
        })

        await self.config.guild_from_id(guild.id).logger_channel_id.set(channel.id)

        await ctx.channel.send(f"New channel {channel.mention} created. Message logs will be stored.")
        return

    @logger.command(usage="<True|False>")
    @commands.mod_or_permissions(manage_roles=True)
    async def inline(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """
        Sets whether or not to use inline formatting for log printouts.
        """
        guild: discord.Guild = ctx.guild
        formatted_inline = await self.config.guild_from_id(guild.id).formatted_inline()

        if bool == None:
            format = "inline" if formatted_inline else "quote"
            await ctx.channel.send(f"Currently using {format} formatting for logs.")
            return

        await self.config.guild_from_id(guild.id).formatted_inline.set(bool)

        if bool:
            await ctx.channel.send(f"Now using inline formatting for logs.")
        else:
            await ctx.channel.send(f"Now using quote formatting for logs.")
        return

    @commands.Cog.listener(name="on_raw_message_delete")
    @commands.Cog.listener(name="on_raw_message_edit")
    async def send_log(self, event: typing.Union[discord.RawMessageUpdateEvent, discord.RawMessageDeleteEvent]):
        """
        Sends data to the logger channel.
        """
        payload = LogPayload(event)
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)

        if await self.config.guild_from_id(guild.id).is_enabled():
            channel: discord.TextChannel = guild.get_channel(
                payload.channel_id)

            logger_channel_id = await self.config.guild_from_id(guild.id).logger_channel_id()
            logger_channel: discord.TextChannel = guild.get_channel(
                logger_channel_id)

            if payload.before == None or payload.before.author == None or payload.before.author.id == None:
                return

            author = await self.bot.get_or_fetch_member(guild, payload.before.author.id)
            if author == None:
                author = await self.bot.get_or_fetch_user(payload.before.author.id)

            if author.bot:
                return

            link_text = ""

            if await self.config.guild_from_id(guild.id).is_links_enabled():
                link_text = f" <{payload.before.jump_url}>"

            log = f"[{channel.mention}] `{payload.type}D` message from **{author.display_name}**{link_text}:"

            if payload.type == 'DELETE':
                await logger_channel.send(log + f"\n{payload.before.content}", files=[await attachment.to_file() for attachment in payload.before.attachments])
                pass
            elif payload.type == 'UPDATE':
                if await self.config.guild_from_id(guild.id).formatted_inline():
                    await logger_channel.send(log + f"\n{payload.delta_inline}")
                else:
                    before = '>>> ' + payload.before.content
                    await logger_channel.send(f"{log}\n{before}")
                    await logger_channel.send(payload.data['content'])
        return

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        Listens for channel deletions to reset logging channel if it was deleted.
        """
        if isinstance(channel, discord.TextChannel):
            guild = channel.guild
            logger_channel_id = await self.config.guild_from_id(guild.id).logger_channel_id()

            if logger_channel_id == channel.id:
                await self.config.guild_from_id(guild.id).logger_channel_id.set(None)

        pass
