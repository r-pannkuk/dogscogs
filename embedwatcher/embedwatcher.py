import collections
from datetime import timedelta
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "timeout_mins": 10
}

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

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.hybrid_group()
    @commands.mod_or_permissions(manage_roles=True)
    async def embedwatcher(self, ctx: commands.Context):
        """Watches for embed edits and deletes messages to prevent them.
        """
        pass

    @embedwatcher.command()
    @commands.mod_or_permissions(manage_roles=True)
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
    @commands.mod_or_permissions(manage_roles=True)
    async def timeout(self, ctx: commands.Context, minutes: typing.Optional[int]):
        """Defines how long a user should be timed out for after editing an embed.

        Args:
            minutes (int): (Optional) How long to timeout the user for. 
        """
        if minutes is None:
            minutes = await self.config.guild(ctx.guild).timeout_mins()

        await self.config.guild(ctx.guild).timeout_mins.set(minutes)

        if minutes > 0:
            await ctx.send(f"Users who edit message embeds will be timed out for {minutes} minute{'' if minutes == 1 else 's'}.")
        else:
            await ctx.send(f"Users will not be timed out if they edit embeds.")

        pass

    @commands.Cog.listener()
    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent):

        guild: discord.Guild = self.bot.get_guild(event.guild_id)
        before = event.cached_message
        after = event.data

        if await self.config.guild_from_id(guild.id).is_enabled():
            if before.author.bot:
                return
            
            before_files = [embed.url for embed in before.embeds]
            before_files.extend([attachment.url for attachment in before.attachments])

            if "embeds" in after:
                after_files = [embed["url"] for embed in after["embeds"]]
            if "attachments" in after:
                after_files.extend([attachment["url"] for attachment in after["attachments"]])

            if collections.Counter(before_files) == collections.Counter(after_files):
                return
            
            message = await before.channel.fetch_message(after["id"])
            await message.delete()
            
            author : dict = after["author"]
            member : discord.Member = await guild.fetch_member(author.get("id"))

            if member:
                timeout_mins = await self.config.guild(guild).timeout_mins()
                
                if timeout_mins > 0:
                    try:
                        reason = f"Embeds are currently prevented from being edited.  User has been timed out for {timeout_mins} minute{'' if timeout_mins == 1 else 's'}."
                        await member.timeout(timedelta(minutes=timeout_mins), reason=reason)
                        await member.send(reason)
                    except:
                        await member.send("Editing embeds is not allowed.")
                    pass
            pass
        pass