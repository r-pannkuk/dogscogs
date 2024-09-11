import asyncio
import datetime
import io
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.constants.discord.channel import TEXT_TYPES as TEXT_CHANNEL_TYPES
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.converters.user import UserList
from dogscogs.converters.channel import TextChannelList

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

CHUNK_SIZE = 100

UPDATE_DURATION_SECS = 5
DELETE_INTERVAL_SECS = 3

class Purge(commands.Cog):
    """
    Purges X posts from a selected channel.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        pass

    def _file_header(
        self,
        users: typing.List[discord.User],
        channel: TEXT_CHANNEL_TYPES,
        messages: typing.List[discord.Message],
    ):
        header = ""
        header += f"Server: {channel.guild.name}\n"
        header += f"Server ID: {channel.guild.id}\n"
        header += f"Channel: {channel.name}\n"
        header += f"Channel ID: {channel.id}\n"
        header += f"Users: \n"

        for user in users:
            header += f"-- {user.display_name}{f'({user.name})' if user.name != user.display_name else ''} [{user.id}]\n"

        header += f"No. Messages: {len(messages)}\n"
        header += "\n\n"

        return header

    def _file_line(self, message: discord.Message):
        user = message.author
        username = f"{user.display_name}{f' ({user.name})' if user.name != user.display_name else ''}"
        return f"({message.created_at.strftime('%Y-%m-%d %H:%M:%S')}) {username}: {message.content}"

    @commands.group()
    @commands.admin_or_can_manage_channel()
    async def purge(self, ctx: commands.GuildContext):
        """Purges messages for the given user or channel

        Args:
            ctx (commands.GuildContext): Command context.
        """

    @purge.command()
    @commands.admin_or_can_manage_channel()
    async def channel(
        self,
        ctx: commands.GuildContext,
        number: int,
        channel: typing.Optional[TEXT_CHANNEL_TYPES],
    ):
        """Deletes up to X messages from the supplied channel (or current channel if none exists).

        Args:
            ctx (commands.GuildContext): Command context.
            number (int): The number of posts to delete.
            channel (typing.Optional[discord.TextChannel]): The channel to delete from.  Defaults to current channel.
        """
        before_message : discord.Message    
        
        if channel is None:
            channel = ctx.channel # type: ignore[assignment]
            before_message = ctx.message
        else:
            before_message = channel.last_message # type: ignore[assignment]

        await ctx.defer(ephemeral=False)

        messages = channel.history(limit=number, before=before_message, oldest_first=False) # type: ignore[union-attr]

        list = []

        async for message in messages:
            list.append(message)

        list.reverse()

        first_deleted_message: discord.Message = list[0]
        last_deleted_message: discord.Message = list[-1]

        number = len(list)

        embed = discord.Embed()
        embed.title = f"Deleting {number} message{'' if number == 1 else 's'}:"
        embed.description = f"Channel: {channel.mention}"  # type: ignore[union-attr]
        embed.description += "\n"
        embed.description += f"First Message: {first_deleted_message.jump_url}"
        embed.description += "\n"
        embed.description += f"Last Message: {last_deleted_message.jump_url}"

        view = ConfirmationView(author=ctx.author)

        prompt = await ctx.send(embed=embed, view=view)

        await view.wait()

        if not view.value:
            await prompt.edit(content="Cancelled.",view=None,delete_after=15)
            return

        # for i in range(0, len(list), CHUNK_SIZE):
        #     chunk = list[i: i + CHUNK_SIZE]
        deleted_messages = await channel.purge( # type: ignore[union-attr]
            limit=number, before=before_message, bulk=True, oldest_first=False
        )
        # await view.response.edit(content=f"{i + CHUNK_SIZE if i + CHUNK_SIZE < number else number} out of {number} deleted.")
        # await asyncio.sleep(3)

        await ctx.channel.send(f"Deleted {len(deleted_messages)} messages.", delete_after=15)
        pass

    @purge.command()
    @commands.admin_or_can_manage_channel()
    async def user(
        self,
        ctx: commands.GuildContext,
        users: typing.Annotated[typing.List[discord.User], UserList],
        in_channels: typing.Optional[typing.Annotated[typing.List[TEXT_CHANNEL_TYPES], TextChannelList]],
        ignore_channels: typing.Optional[typing.Annotated[typing.List[TEXT_CHANNEL_TYPES], TextChannelList]],
        limit: typing.Optional[int],
    ):
        """Purges messages for given users in channels

        Args:
            ctx (commands.GuildContext): Command Context
            users (typing.List[discord.Member]): The list of users to purge.
            inChannels (typing.Optional[typing.List[discord.TextChannel]]): (optional) The channels to screen for.
            ignoreChannels (typing.Optional[typing.List[discord.TextChannel]]): (optional) The channels to not include.
            limit (typing.Optional[int]): (optional) A limit on how many messages to purge.
        """
        if in_channels is None:
            in_channels = [c for c in ctx.guild.channels if isinstance(c, TEXT_CHANNEL_TYPES)]

        in_channels = [
            channel
            for channel in in_channels
            if channel.permissions_for(ctx.me).read_messages
            and channel.permissions_for(ctx.me).read_message_history
            and channel.permissions_for(ctx.me).manage_messages
        ]

        if ignore_channels is not None:
            in_channels = [
                channel
                for channel in in_channels
                if channel.id not in [channel.id for channel in ignore_channels]
            ]

        in_channels.sort(key=lambda c: c.position if hasattr(c, 'position') else -1)

        messages : typing.Dict[int, typing.List[discord.Message]] = {}
        number = 0

        deferment = await ctx.send("Starting fetch")

        user_ids : typing.List[int] = [user.id for user in users]

        response = await ctx.channel.send("Fetching...")

        for channel in in_channels:
            await response.edit(content=f"Fetching...{channel.mention}")
            messages[channel.id] = []
            channel_scan_number = 0
            author_scan_number = 0

            next_update = datetime.datetime.now() + datetime.timedelta(seconds=UPDATE_DURATION_SECS)

            # Start with current message and then go backwards
            message = ctx.message

            history = channel.history(limit=None, before=message, oldest_first=False)

            while True:
                try:
                    result = await anext(history)
                    
                    message = result
                    
                    channel_scan_number += 1

                    if datetime.datetime.now() > next_update:
                        await response.edit(content=f"Fetching...{channel.mention}\nParsed: {channel_scan_number}\nFound: {author_scan_number}")
                        next_update = datetime.datetime.now() + datetime.timedelta(seconds=UPDATE_DURATION_SECS)
                    
                    if message.author.id in user_ids:
                        messages[channel.id].append(message)
                        number += 1
                        author_scan_number += 1

                        if limit is not None and author_scan_number >= limit:
                            break
                except StopAsyncIteration as e:
                    break
                except Exception as e:
                    history = channel.history(limit=None, before=message, oldest_first=False)
                    continue

        if number == 0:
            await ctx.channel.delete_messages([response])
            await ctx.send("No messages found.")
            return

        channel_mentions = [f"{channel.mention} ({len(messages[channel.id])})" for channel in in_channels]

        embed = discord.Embed()
        embed.title = f"Deleting {number} message{'' if number == 1 else 's'}:"
        embed.description = f"**User**: {', '.join([user.mention for user in users])}"
        embed.description += f"\n"
        embed.description += f"**Channels**: {', '.join(channel_mentions)}"
        embed.description += f"\n"
        embed.description += f"**Number**: {number}"

        view = ConfirmationView(author=ctx.author)

        prompt = await ctx.send(embed=embed, view=view)

        await view.wait()

        if view.value:
            completed_channels: typing.List[TEXT_CHANNEL_TYPES] = []
            current_total = 0

            followup = await ctx.channel.send("Starting...")

            def generate_followup_str(
                channel, channel_current_total, channel_total, current_total
            ) -> str:
                followup_str = f"**Completed**: {', '.join([channel.mention for channel in completed_channels])}"
                followup_str += f"\n"
                followup_str += f"**Currently On**: {channel.mention} ({channel_current_total} out of {channel_total})"
                followup_str += f"\n"
                followup_str += f"**Total**: {current_total} out of {number}"
                return followup_str

            for id, msgs in messages.items():
                channel = ctx.guild.get_channel(id) # type: ignore[assignment]
                channel_total = len(msgs)
                channel_current_total = 0
                update_duration_secs = UPDATE_DURATION_SECS

                await followup.edit(
                    content=generate_followup_str(
                        channel, channel_current_total, channel_total, current_total
                    )
                )

                if len(msgs) > 0:
                    file = self._file_header(users, channel, msgs)

                    bulk_messages = [
                        message
                        for message in msgs
                        if message.created_at
                        > (datetime.datetime.now() - datetime.timedelta(days=14))
                    ]

                    file += "\n".join(
                        [self._file_line(message) for message in bulk_messages]
                    )

                    await channel.delete_messages(bulk_messages)

                    channel_current_total += len(bulk_messages)
                    current_total += len(bulk_messages)

                    remaining_messages = [
                        message for message in msgs if message not in bulk_messages
                    ]

                    for message in remaining_messages:
                        file += self._file_line(message) + "\n"
                        attempts = 0

                        while True:
                            try:
                                attempts += 1
                                await message.delete()
                                break
                            # except discord.RateLimited as e:
                            #     print(e)
                            #     await asyncio.sleep(e.retry_after)
                            except Exception as e:
                                print(e)
                                if attempts > 10:
                                    break

                        channel_current_total += 1
                        current_total += 1

                        try:
                            if datetime.datetime.now() > next_update:
                                await followup.edit(
                                    content=generate_followup_str(
                                        channel,
                                        channel_current_total,
                                        channel_total,
                                        current_total,
                                    )
                                )
                                next_update = datetime.datetime.now() + datetime.timedelta(seconds=update_duration_secs)

                        except Exception as e:
                            await followup.delete()
                            followup = ctx.send(content=generate_followup_str(
                                channel,
                                channel_current_total,
                                channel_total,
                                current_total,
                            ))
                            pass

                        await asyncio.sleep(DELETE_INTERVAL_SECS)

                    f = io.StringIO(file)
                    await ctx.author.send(
                        file=discord.File(
                            fp=f, # type: ignore[arg-type]
                            filename=f"{channel.name}_{int(datetime.datetime.now().strftime('%Y%m%d'))}.txt",
                        )
                    )

                completed_channels.append(channel)

            await prompt.edit(content="Deleted.",view=None,delete_after=15)
            pass
        else:
            await prompt.edit(content=f"Cancelled.",view=None,delete_after=15)
            pass
        pass

        pass
