import collections
from datetime import timedelta
import datetime
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from types import SimpleNamespace

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "timeout_mins": 10,
    "delay_mins": 60,
    "whitelist": {
        "channel_ids": [],
        "role_ids": [],
        "user_ids": [],
    },
    "channel_id": None,
}


class ParsedMention(commands.Converter):
    async def convert(
        self, ctx: commands.Context, mention: str
    ) -> typing.Union[discord.TextChannel, discord.Member, discord.Role]:
        try:
            converter = commands.TextChannelConverter()
            return await converter.convert(ctx, mention)
        except:
            pass

        try:
            converter = commands.MemberConverter()
            return await converter.convert(ctx, mention)
        except:
            pass

        try:
            converter = commands.RoleConverter()
            return await converter.convert(ctx, mention)
        except:
            pass

        raise commands.BadArgument("Not a valid mention.")


class EmbedWatcher(commands.Cog):
    """
    Watches for embed edits to lock them.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        await super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.hybrid_group()
    @commands.has_guild_permissions(manage_roles=True)
    async def embedwatcher(self, ctx: commands.Context):
        """Watches for embed edits and deletes messages to prevent them."""
        pass

    @embedwatcher.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, is_enabled: typing.Optional[bool]):
        """Enables or disables the watcher.

        Args:
            is_enabled (typing.Optional[bool]): (Optional) Whether or not to enable this.
        """
        if is_enabled is None:
            is_enabled = await self.config.guild(ctx.guild).is_enabled()

        status_msg = ""

        if is_enabled:
            status_msg = "**ENABLED**"
        else:
            status_msg = "**DISABLED**"

        await self.config.guild(ctx.guild).is_enabled.set(is_enabled)

        await ctx.send(f"Embed watching is currently {status_msg}.")

        pass

    @embedwatcher.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def timeout(self, ctx: commands.Context, minutes: typing.Optional[int]):
        """Defines how long a user should be timed out for after editing an embed.

        Args:
            minutes (int): (Optional) How long to timeout the user for.
        """
        if minutes is None:
            minutes = await self.config.guild(ctx.guild).timeout_mins()

        if minutes < 0:
            minutes = 0

        await self.config.guild(ctx.guild).timeout_mins.set(minutes)

        if minutes > 0:
            await ctx.send(
                f"Users who edit message embeds will be timed out for {minutes} minute{'' if minutes == 1 else 's'}."
            )
        else:
            await ctx.send(f"Users will not be timed out if they edit embeds.")

        pass

    @embedwatcher.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def delay(self, ctx: commands.Context, minutes: typing.Optional[int]):
        """Defines how long the bot should wait before checking for edits.

        Args:
            minutes (int): (Optional) How long to delay edit checks for.
        """
        if minutes is None:
            minutes = await self.config.guild(ctx.guild).delay_mins()

        if minutes < 0:
            minutes = 0

        await self.config.guild(ctx.guild).delay_mins.set(minutes)

        if minutes > 0:
            await ctx.send(
                f"Will wait for {minutes} minute{'' if minutes == 1 else 's'} before checking edited messages."
            )
        else:
            await ctx.send(f"Will not wait to check edited messages.")

        pass

    @embedwatcher.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel(
        self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel]
    ):
        """Sets up an echo channel to announce when users attempt to edit embeds.

        Args:
            channel (discord.TextChannel): (Optional) The channel for announcements.
        """
        if channel is None:
            channel_id = await self.config.guild(ctx.guild).channel_id()
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
            except:
                channel = None
                channel_id = None
            pass
        else:
            channel_id = channel.id

        await self.config.guild(ctx.guild).channel_id.set(channel_id)

        if channel is None:
            await ctx.send(f"Not announcing embed edit attempts to any channel.")
        else:
            await ctx.send(f"Announcing embed edit attempts to {channel.mention}.")

        pass

    @embedwatcher.group()
    @commands.has_guild_permissions(manage_roles=True)
    async def whitelist(self, ctx: commands.Context):
        """Defines the channel whitelist for edited attachments."""
        pass

    @whitelist.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def add(self, ctx: commands.Context, target: ParsedMention):
        """Adds a channel to the white list so it is ignored in scanning attachment changes.

        Args:
            channel (discord.TextChannel): The discord channel to add.
        """
        whitelist = await self.config.guild(ctx.guild).whitelist()

        if isinstance(target, discord.Member):
            whitelist["user_ids"].append(target.id)
            pass
        elif isinstance(target, discord.TextChannel):
            whitelist["channel_ids"].append(target.id)
            pass
        elif isinstance(target, discord.Role):
            whitelist["role_ids"].append(target.id)
            pass
        else:
            raise commands.BadArgument("This is not a valid target for the whitelist.")

        whitelist["user_ids"] = list(set(whitelist["user_ids"]))
        whitelist["channel_ids"] = list(set(whitelist["channel_ids"]))
        whitelist["role_ids"] = list(set(whitelist["role_ids"]))

        await self.config.guild(ctx.guild).whitelist.set(whitelist)

        await ctx.send(f"Added {target.mention} to the whitelist.")
        pass

    @whitelist.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def remove(self, ctx: commands.Context, target: ParsedMention):
        """Removes a channel from the white list so it is scanned for attachment changes.

        Args:
            channel (discord.TextChannel): The discord channel to add.
        """
        whitelist = await self.config.guild(ctx.guild).whitelist()

        BAD_ARGUMENT = "This is not a valid target for the whitelist."

        def remove_from_list(list: typing.List[str]):
            if target.id not in list:
                raise commands.BadArgument(f"That isn't in the whitelist, idiot.")

            list.remove(target.id)

            return list

        if isinstance(target, discord.Member):
            whitelist["user_ids"] = remove_from_list(whitelist["user_ids"])
            pass
        elif isinstance(target, discord.TextChannel):
            whitelist["channel_ids"] = remove_from_list(whitelist["channel_ids"])
            pass
        elif isinstance(target, discord.Role):
            whitelist["role_ids"] = remove_from_list(whitelist["role_ids"])
            pass
        else:
            raise commands.BadArgument(BAD_ARGUMENT)

        await self.config.guild(ctx.guild).whitelist.set(whitelist)

        await ctx.send(f"Removed {target.mention} from the whitelist.")
        pass

    @whitelist.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def list(self, ctx: commands.Context):
        """Lists all channels currently being ignored in attachment change scans."""
        embed = discord.Embed()
        embed.title = f"Whitelist for Embed / Attachment Scans:"

        whitelist = await self.config.guild(ctx.guild).whitelist()

        T = typing.TypeVar("T", discord.TextChannel, discord.Member, discord.Role)

        async def get_list(
            list: typing.List[str],
            fetch: typing.Callable[
                [int], typing.Coroutine[typing.Any, typing.Any, int]
            ],
        ) -> typing.List[T]:
            objects: typing.List[T] = []
            for i in range(len(list)):
                try:
                    object: T = await fetch(list[i])
                    objects.append(object)
                except:
                    continue
            return objects

        channels: typing.List[discord.TextChannel] = await get_list(
            whitelist["channel_ids"], ctx.guild.fetch_channel
        )
        channels.sort(key=lambda channel: channel.name.lower())
        channels = [channel.mention for channel in channels]

        members: typing.List[discord.Member] = await get_list(
            whitelist["user_ids"], ctx.guild.fetch_member
        )
        members.sort(key=lambda member: member.display_name.lower())
        members = [member.mention for member in members]

        roles: typing.List[discord.Role] = await ctx.guild.fetch_roles()
        roles.sort(key=lambda role: role.name.lower())
        roles = [
            roles[i].mention
            for i in range(len(roles))
            if roles[i].id in whitelist["role_ids"]
        ]

        if len(channels) == len(members) == len(roles) == 0:
            await ctx.send(f"There's nothing in the whitelist.")
            return

        embed.add_field(name="Channels", value="\n".join(channels))
        embed.add_field(name="Members", value="\n".join(members))
        embed.add_field(name="Roles", value="\n".join(roles))

        await ctx.send(embed=embed)
        pass

    @commands.Cog.listener()
    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent):
        if isinstance(event, discord.RawMessageDeleteEvent):
            return
        
        if event.guild_id is None:
            return

        guild: discord.Guild = self.bot.get_guild(event.guild_id)
        before = event.cached_message
        after = event.data

        if (
            "author" not in after
            or "embeds" not in after
            or "content" not in after
            or "attachments" not in after
            or "edited_timestamp" not in after
            or ("pinned" in after and after["pinned"] == True)
            or ("pinned" in after and before is not None and before.pinned != after["pinned"])
        ):
            return

        if "bot" not in after["author"]:
            after["author"]["bot"] = False

        if before is None:
            before = SimpleNamespace(
                **{
                    "author": SimpleNamespace(**after["author"]),
                    "embeds": [],
                    "attachments": [],
                    "content": "",
                    "channel_id": after["channel_id"],
                    "id": after["id"],
                    "created_at": datetime.datetime(
                        year=2000,
                        month=1,
                        day=1,
                        hour=1,
                        minute=1,
                        second=1,
                        microsecond=1,
                    ),
                }
            )

        delay_mins = await self.config.guild(guild).delay_mins()

        # ignore delay
        if after["edited_timestamp"] is not None:
            after_edited_at = datetime.datetime.fromisoformat(str(after["edited_timestamp"]))
        else:
            after_edited_at = datetime.datetime.now()
        before_created_at = before.created_at
        if (after_edited_at.timestamp() - before_created_at.timestamp()) <= timedelta(
            minutes=delay_mins
        ).total_seconds():
            return

        # ignore whitelist
        whitelist = await self.config.guild(guild).whitelist()
        if int(after["channel_id"]) in whitelist["channel_ids"]:
            return
        if int(after["author"]["id"]) in whitelist["user_ids"]:
            return
        
        author: dict = after["author"]
        try:
            member: discord.Member = await guild.fetch_member(author.get("id"))
        except:
            return
        member_role_ids = [role.id for role in member.roles]

        if True in (role_id in whitelist["role_ids"] for role_id in member_role_ids):
            return

        if await self.config.guild_from_id(guild.id).is_enabled():
            if member.bot:
                return

            before_files = [embed.url for embed in before.embeds]
            before_files.extend([attachment.url for attachment in before.attachments])

            if "embeds" in after:
                after_files = [embed["url"] for embed in after["embeds"]]
            if "attachments" in after:
                after_files.extend(
                    [attachment["url"] for attachment in after["attachments"]]
                )

            if collections.Counter(before_files) == collections.Counter(after_files):
                return

            try:
                channel = await guild.fetch_channel(after["channel_id"])
                message = await channel.fetch_message(after["id"])
                jump_url = message.jump_url
                await message.delete()
            except:
                return

            if member:
                timeout_mins = await self.config.guild(guild).timeout_mins()

                if timeout_mins > 0:
                    try:
                        reason = f"Embeds are currently prevented from being edited.  User has been timed out for {timeout_mins} minute{'' if timeout_mins == 1 else 's'}."
                        await member.timeout(
                            timedelta(minutes=timeout_mins), reason=reason
                        )
                        await member.send(reason)
                    except:
                        await member.send("Editing embeds is not allowed.")
                    pass

            channel_id = await self.config.guild(guild).channel_id()

            if channel_id is not None:
                try:
                    channel = await guild.fetch_channel(channel_id)
                except:
                    await self.config.guild(guild).channel_id.set(None)
                    return

                response = f"User {member.mention if member else author} {f'was timedout for {timeout_mins} mins for' if timeout_mins else ''} attempting to edit an embed / attachment in {jump_url}:\n"
                response += ">>> " + before.content
                await channel.send(response, suppress_embeds=True)
                await channel.send(after["content"], suppress_embeds=True)
            pass
        pass
