import collections
from datetime import timedelta
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.converters.mention import Mention


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

class EmbedWatcher(commands.Cog):
    """
    Watches for embed edits to lock them.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
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
    async def embedwatcher(self, ctx: commands.GuildContext):
        """Watches for embed edits and deletes messages to prevent them."""
        pass

    @embedwatcher.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.GuildContext, is_enabled: typing.Optional[bool]):
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
    async def timeout(self, ctx: commands.GuildContext, minutes: typing.Optional[int]):
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
    async def delay(self, ctx: commands.GuildContext, minutes: typing.Optional[int]):
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
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """Sets up an echo channel to announce when users attempt to edit embeds.

        Args:
            channel (discord.TextChannel): (Optional) The channel for announcements.
        """
        if channel is None:
            channel_id = await self.config.guild(ctx.guild).channel_id()
            try:
                channel = await ctx.guild.fetch_channel(channel_id)  # type: ignore[assignment]
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
    async def whitelist(self, ctx: commands.GuildContext):
        """Defines the channel whitelist for edited attachments."""
        pass

    @whitelist.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def add(self, ctx: commands.GuildContext, target: Mention):
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

        await ctx.send(f"Added {target.mention} to the whitelist.") # type: ignore[attr-defined]
        pass

    @whitelist.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def remove(self, ctx: commands.GuildContext, target: typing.Annotated[typing.Union[
            discord.TextChannel,
            discord.Member,
            discord.Role,
        ], Mention]):
        """Removes a channel from the white list so it is scanned for attachment changes.

        Args:
            channel (discord.TextChannel): The discord channel to add.
        """
        whitelist = await self.config.guild(ctx.guild).whitelist()

        BAD_ARGUMENT = "This is not a valid target for the whitelist."

        def remove_from_list(list: typing.List[int]):
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
    async def list(self, ctx: commands.GuildContext):
        """Lists all channels currently being ignored in attachment change scans."""
        embed = discord.Embed()
        embed.title = f"Whitelist for Embed / Attachment Scans:"

        whitelist = await self.config.guild(ctx.guild).whitelist()

        T = typing.TypeVar("T", discord.TextChannel, discord.Member, discord.Role)

        async def get_list(
            list: typing.List[int],
            fetch: typing.Callable[
                [int], typing.Coroutine[typing.Any, typing.Any, T]
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
            whitelist["channel_ids"], ctx.guild.fetch_channel  # type: ignore[arg-type]
        ) 
        channels.sort(key=lambda channel: channel.name.lower())
        channel_mentions = [channel.mention for channel in channels]

        members: typing.List[discord.Member] = await get_list(
            whitelist["user_ids"], ctx.guild.fetch_member
        )
        members.sort(key=lambda member: member.display_name.lower())
        member_mentions = [member.mention for member in members]

        roles: typing.List[discord.Role] = await ctx.guild.fetch_roles()
        roles.sort(key=lambda role: role.name.lower())
        role_mentions = [
            roles[i].mention
            for i in range(len(roles))
            if roles[i].id in whitelist["role_ids"]
        ]

        if len(channel_mentions) == len(member_mentions) == len(role_mentions) == 0:
            await ctx.send(f"There's nothing in the whitelist.")
            return

        embed.add_field(name="Channels", value="\n".join(channel_mentions))
        embed.add_field(name="Members", value="\n".join(member_mentions))
        embed.add_field(name="Roles", value="\n".join(role_mentions))

        await ctx.send(embed=embed)
        pass

    async def _process_message(
        self,
        before: typing.Optional[discord.Message],
        after: discord.Message,
        delete=True,
    ):
        guild = after.guild

        if guild is None:
            return

        member = after.author
        jump_url = after.jump_url

        try:
            if delete:
                await after.delete()
        except:
            return

        if member:
            timeout_mins = await self.config.guild(guild).timeout_mins()

            if timeout_mins > 0:
                try:
                    reason = f"Embeds are currently prevented from being edited.  User has been timed out for {timeout_mins} minute{'' if timeout_mins == 1 else 's'}."
                    await member.timeout(timedelta(minutes=timeout_mins), reason=reason) # type: ignore[union-attr]
                    await member.send(reason)
                except:
                    await member.send("Editing embeds is not allowed.")
                pass

            channel_id = await self.config.guild(guild).channel_id()

            if channel_id is not None:
                try:
                    echo_channel: discord.TextChannel = await guild.fetch_channel(channel_id)  # type: ignore[assignment]
                except:
                    await self.config.guild(guild).channel_id.set(None)
                    return

                response = f"User {member.mention if member else after.author.id} {f'was timed out for {timeout_mins} mins for' if timeout_mins else ''} attempting to edit an embed / attachment in {jump_url}:\n\n"
                if before:
                    response += ">>> " + before.content + "\n\n"
                else:
                    response += "``MESSAGE WAS NOT CACHED``\n\n"

                await echo_channel.send(response, suppress_embeds=True)
                await echo_channel.send(after.content, suppress_embeds=True)
            pass
        pass

    @commands.Cog.listener()
    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent):
        if isinstance(event, discord.RawMessageDeleteEvent):
            return

        if event.guild_id is None:
            return

        guild = self.bot.get_guild(event.guild_id)

        if guild is None:
            return

        before = event.cached_message
        after = event.data
        channel = self.bot.get_channel(event.channel_id)
        try:
            message : discord.Message = await channel.fetch_message(int(after['id'])) # type: ignore[union-attr]
        except:
            return

        if message is None:
            return

        # Return if:
        # - author is not in after
        # - embeds is not in after
        # - content is not in after
        # - attachments is not in after
        # - edited_timestamp is not in after
        # - pinned is in after and is True
        # - pinned is in after and before is not None and before.pinned != after["pinned"]

        # Reconstruct before if it's not found (no cache)

        # Returning if the channel ID or author ID was in the whitelist
        whitelist = await self.config.guild(guild).whitelist()
        if int(event.channel_id) in whitelist["channel_ids"]:
            return

        if message.author.id in whitelist["user_ids"]:
            return

        if message.author.bot:
            return
        
        member = guild.get_member(message.author.id)

        member_role_ids : typing.List[int] = [role.id for role in member.roles] # type: ignore[union-attr]

        # Returning if the author's roles match any of the whitelist.
        if True in (role_id in whitelist["role_ids"] for role_id in member_role_ids):
            return

        if await self.config.guild_from_id(guild.id).is_enabled():
            delay_mins: float = await self.config.guild(guild).delay_mins()
            edited_at = message.edited_at
            created_at = message.created_at
            
            if edited_at is None:
                return

            if (edited_at - created_at).total_seconds() <= timedelta(
                minutes=delay_mins
            ).total_seconds():
                return
            
            delete = True

            # Message is cached.
            if before:
                before_files = []
                if before.embeds:
                    before_files.extend([embed.url for embed in before.embeds])
                if before.attachments:
                    before_files.extend(
                        [attachment.url for attachment in before.attachments]
                    )

                after_files = []

                if message.embeds is not None:
                    after_files.extend([embed.url for embed in message.embeds])
                if message.attachments is not None:
                    after_files.extend(
                        [attachment.url for attachment in message.attachments]
                    )

                before_files = list(set(before_files))
                after_files = list(set(after_files))

                if collections.Counter(before_files) == collections.Counter(
                    after_files
                ):
                    return
            # Message is not cached.
            else:
                # delete = False
                pass

            await self._process_message(before, message, delete)  # type: ignore[arg-type]
        pass
