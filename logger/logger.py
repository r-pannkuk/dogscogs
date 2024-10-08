import json
from typing import Literal
import typing

import discord
from discord.permissions import PermissionOverwrite
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "is_links_enabled": True,
    "logger_channel_id": None,
    "logger_channel_name": "logs",
    "formatted_inline": True,
}

FORMAT_ADDED = "`"
FORMAT_REMOVED = "~~"


class CachedMessageDict(typing.TypedDict):
    content: str
    attachments: typing.List[discord.Attachment]


LogType = Literal["UPDATE", "DELETE"]


class LogPayload:
    """What type of event this is."""
    type: LogType

    """The author id"""
    author_id: typing.Union[int, None]

    """The guild ID that this message was from."""
    guild_id: int

    """The channel ID that this message was from."""
    channel_id: int

    """The message prior to the event."""
    before: CachedMessageDict

    """The url to the message."""
    jump_url: str

    """The message after the event."""
    data : typing.Optional[typing.Any]

    def __init__(
        self,
        event: typing.Union[
            discord.RawMessageUpdateEvent, discord.RawMessageDeleteEvent
        ],
    ) -> None:
        if isinstance(event, discord.RawMessageUpdateEvent):
            self.type = "UPDATE"
            self.author_id = int(event.data["author"]["id"])
            self.before = {
                "content": (
                    event.cached_message.content
                    if event.cached_message
                    else "<<< Message was not cached. >>>"
                ),
                "attachments": (
                    event.cached_message.attachments if event.cached_message else []
                ),
            }
            self.data = event.data
        elif isinstance(event, discord.RawMessageDeleteEvent):
            self.type = "DELETE"
            self.author_id = event.cached_message.author.id if event.cached_message else None
            self.before = {
                "content": (
                    event.cached_message.content
                    if event.cached_message
                    else "<<< Message was not cached. >>>"
                ),
                "attachments": (
                    event.cached_message.attachments if event.cached_message else []
                ),
            }
            self.data = None  # type: ignore[assignment]
        else:
            raise ValueError("Invalid event type.")
        
        self.jump_url = f"https://discord.com/channels/{event.guild_id}/{event.channel_id}/{event.message_id}"
        self.guild_id = event.guild_id # type: ignore[assignment]
        self.channel_id = event.channel_id

        return

    @property
    def delta_inline(self) -> str:
        """
        The formatted output to print out for logging.
        """
        import difflib

        expected = self.before["content"]
        actual : str = (
            ""
            if self.data is None
            or "content" not in self.data
            or self.data["content"] == None
            else self.data["content"]
        )
        text = ""
        prev = "  "
        for ele in difflib.Differ().compare(expected, actual):
            comparator = ele[:2]

            if comparator == "  ":
                if prev == "+ ":
                    text += FORMAT_ADDED
                text += f"{ele[2:]}"
            elif comparator == "- ":
                if prev == "+ ":
                    text += FORMAT_ADDED
                text += f"{FORMAT_REMOVED}{ele[2:]}{FORMAT_REMOVED}"
            elif comparator == "+ ":
                if prev == "  " or prev == "- ":
                    text += FORMAT_ADDED
                text += f"{ele[2:]}"

            prev = comparator

        if prev == "+ ":
            text += FORMAT_ADDED
        return text


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
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def logger(self, ctx):
        """
        Handles logging for message deletions and edits in the server.
        """
        pass

    @logger.command(usage="<True|False>")
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.GuildContext, bool: typing.Optional[bool]):
        """
        Sets whether or not logging is eanbled for deleted / edited messages.
        """
        guild: discord.Guild = ctx.guild
        is_enabled = await self.config.guild_from_id(guild.id).is_enabled()

        logger_channel_id = await self.config.guild_from_id(
            guild.id
        ).logger_channel_id()
        prefix = await ctx.bot.get_prefix(ctx.message)

        if isinstance(prefix, list):
            prefix = prefix[0]

        channel_unset_message = f"Please set a logging channel using `{prefix}logger channel <channel>` or create one with `{prefix}logger create <name>`."

        if logger_channel_id is not None:
            logger_channel = guild.get_channel(logger_channel_id)
            if logger_channel is None:
                await self.config.guild_from_id(guild.id).logger_channel_id.set(None)
                await ctx.channel.send(
                    f"Logger channel currently set to a channel that no longer exists. {channel_unset_message}"
                )
                return
            channel_set_message = f"Logs will be displayed in {logger_channel.mention}."

        if bool == None:
            status = "**ENABLED**" if is_enabled else "**DISABLED**"
            if is_enabled:
                if logger_channel_id == None:
                    status += f".  {channel_unset_message}"
                else:
                    status += f".  {channel_set_message}"
            await ctx.channel.send(
                f"Logging of message edits and deletions is currently {status}"
            )
            return

        await self.config.guild_from_id(guild.id).is_enabled.set(bool)

        if bool:
            str = f"Now logging message edits and deletions."
            logger_channel_id = await self.config.guild_from_id(
                guild.id
            ).logger_channel_id()

            if logger_channel_id == None:
                str += f" {channel_unset_message}"
            else:
                str += f"  {channel_set_message}"

            await ctx.channel.send(str)
        else:
            await ctx.channel.send(f"No longer logging message edits and deletions.")
        return

    @logger.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def enable(self, ctx: commands.GuildContext):
        """
        Enables logging for this bot.
        """
        await self.enabled(ctx, True)
        return

    @logger.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def disable(self, ctx: commands.GuildContext):
        """
        Disables logging for this bot.
        """
        await self.enabled(ctx, False)
        return

    @logger.command(name="links", usage="<True|False>")
    @commands.has_guild_permissions(manage_roles=True)
    async def links_enabled(self, ctx: commands.GuildContext, bool: typing.Optional[bool]):
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
            await ctx.channel.send(
                f"No longer displaying links in edit and deletion logs."
            )
        return

    @logger.command(usage="<channel>")
    @commands.has_guild_permissions(manage_roles=True)
    async def channel(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Sets the logger channel to a specified channel on the server. If no channel is provided, it will display what channel is currently set.
        """
        guild: discord.Guild = ctx.guild

        if channel is None:
            channel = guild.get_channel(await self.config.guild(guild).logger_channel_id) # type: ignore[assignment]

            if channel is None:
                await ctx.channel.send(
                    f"No logger channel set. Please create one with `{ctx.prefix}logger create <name>`."
                )
                return
            
        await self.config.guild_from_id(guild.id).logger_channel_id.set(channel.id)
        await ctx.channel.send(f"Logger channel set to {channel.mention}.")
        return

    @logger.command(usage="<name>")
    @commands.has_guild_permissions(manage_roles=True)
    async def create(self, ctx: commands.GuildContext, name: typing.Optional[str]):
        """
        Creates a new logger channel to store message edits and deletions in.
        """
        guild: discord.Guild = ctx.guild

        if name is None:
            name = await self.config.guild(guild).logger_channel_name()

        channels: typing.List[discord.guild.GuildChannel] = [
            c for c in guild.channels if c.name == name
        ]

        if len(channels) > 0:
            await ctx.channel.send(
                f"Already found existing channel with name {channels[0].mention}. Please use a different name."
            )
            return

        channel = await guild.create_text_channel(
            name=name,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False, send_messages=False, view_channel=False
                )
            },
        )

        await self.config.guild_from_id(guild.id).logger_channel_id.set(channel.id)

        await ctx.channel.send(
            f"New channel {channel.mention} created. Message logs will be stored."
        )
        return

    @logger.command(usage="<True|False>")
    @commands.has_guild_permissions(manage_roles=True)
    async def inline(self, ctx: commands.GuildContext, bool: typing.Optional[bool]):
        """
        Sets whether or not to use inline formatting for log printouts.
        """
        guild: discord.Guild = ctx.guild

        if bool == None:
            bool = await self.config.guild_from_id(guild.id).formatted_inline()

        await self.config.guild_from_id(guild.id).formatted_inline.set(bool)
        await ctx.channel.send(f"Now using {'inline' if bool else 'quote'} formatting for logs.")
        return

    @commands.Cog.listener(name="on_raw_message_delete")
    @commands.Cog.listener(name="on_raw_message_edit")
    async def send_log(
        self,
        event: typing.Union[
            discord.RawMessageUpdateEvent, discord.RawMessageDeleteEvent
        ],
    ):
        """
        Sends data to the logger channel.
        """
        if event.guild_id is None:
            return

        guild: discord.Guild = self.bot.get_guild(event.guild_id) # type: ignore[assignment]

        if guild == None:
            return

        if await self.config.guild_from_id(guild.id).is_enabled():
            payload = LogPayload(event)

            channel: discord.TextChannel = guild.get_channel_or_thread(payload.channel_id) #type: ignore[assignment]

            logger_channel_id = await self.config.guild(guild).logger_channel_id()
            logger_channel = guild.get_channel(logger_channel_id)

            if logger_channel is None:
                return

            author_id = payload.author_id

            if author_id is None:
                return
            
            author : typing.Union[discord.Member, discord.User]

            try:
                author = await self.bot.get_or_fetch_member(guild, author_id)
            except discord.errors.NotFound:
                author = await self.bot.get_or_fetch_user(author_id)

            if author.bot:
                return

            link_text = ""

            if await self.config.guild_from_id(guild.id).is_links_enabled():
                link_text = payload.jump_url

            log = f"[{channel.mention if channel is not None else '`UNKNOWN`'}] `{payload.type}D` message from **{author.display_name}** {link_text}:"

            no_mentions = discord.AllowedMentions.none()

            if payload.type == "DELETE":
                await logger_channel.send( # type: ignore[union-attr]
                    log + f"\n{payload.before['content']}",
                    files=[
                        await attachment.to_file()
                        for attachment in payload.before["attachments"]
                    ],
                    suppress_embeds=True,
                    allowed_mentions=no_mentions
                )
                pass
            elif payload.type == "UPDATE":
                if await self.config.guild_from_id(guild.id).formatted_inline():
                    await logger_channel.send( # type: ignore[union-attr]
                        log + f"\n{payload.delta_inline}", suppress_embeds=True
                    )
                else:
                    before = ">>> " + payload.before["content"]
                    after = (
                        "`No content provided.`"
                        if payload.data is None
                        or "content" not in payload.data
                        or payload.data["content"] is None
                        or payload.data["content"] == ""
                        else payload.data["content"]
                    )
                    await logger_channel.send(f"{log}\n{before}", suppress_embeds=True, allowed_mentions=no_mentions) # type: ignore[union-attr]
                    try:
                        await logger_channel.send(after, suppress_embeds=True, allowed_mentions=no_mentions) # type: ignore[union-attr]
                    except Exception as e:
                        print(f"Failed to print message. Dumping:\n\n{payload}\n\n")
                        raise e
        return

    @commands.Cog.listener(name="on_raw_bulk_message_delete")
    async def send_bulk_delete_log(self, event: discord.RawBulkMessageDeleteEvent):
        """
        Sends bulk data for processing.
        """
        if event.guild_id is None:
            return

        for message in event.cached_messages:
            single_event: discord.RawMessageDeleteEvent = discord.RawMessageDeleteEvent(
                {
                    "channel_id": event.channel_id,
                    "guild_id": event.guild_id,
                    "id": message.id,
                }
            )
            single_event.cached_message = message

            await self.send_log(single_event)
        pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        Listens for channel deletions to reset logging channel if it was deleted.
        """
        if isinstance(channel, discord.TextChannel):
            guild = channel.guild
            logger_channel_id = await self.config.guild_from_id(
                guild.id
            ).logger_channel_id()

            if logger_channel_id == channel.id:
                await self.config.guild_from_id(guild.id).logger_channel_id.set(None)

        pass
