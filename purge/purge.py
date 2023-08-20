import asyncio
import datetime
import io
import os
import tempfile
from typing import Literal
import typing

import discord
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

CHUNK_SIZE = 100
TEXT_CHANNEL_TYPES = [
    discord.ChannelType.forum,
    discord.ChannelType.news,
    discord.ChannelType.news_thread,
    discord.ChannelType.public_thread,
    discord.ChannelType.text,
]


class ChannelParser(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        channels = ctx.guild.channels
        args = argument.split()

        channel_list = [
            channel
            for channel in channels
            if channel.mention in args or channel.id in args
        ]
        args = [
            arg
            for arg in args
            if not arg in [channel.mention for channel in channel_list]
        ]

        if len(args) > 0:
            raise commands.BadArgument(f"No channels were found for: {','.join(args)}")

        bad_channels = [
            channel
            for channel in channel_list
            if channel.type not in TEXT_CHANNEL_TYPES
        ]

        if len(bad_channels) > 0:
            raise commands.BadArgument(
                f"Can't read messages for {','.join(bad_channels)}"
            )

        return channel_list


class UserParser(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        users = ctx.guild.members
        args = argument.split()

        user_list = [user for user in users if user.mention in args or user.id in args]
        args = [arg for arg in args if not arg in [user.mention for user in user_list]]

        if len(args) > 0:
            pruned_args = [
                id.replace("<", "").replace(">", "").replace("@", "") for id in args
            ]
            extra_users = [await ctx.bot.fetch_user(arg) for arg in pruned_args]

            badUsers = []

            for i in range(len(extra_users)):
                user = extra_users[i]
                if user is None:
                    badUsers.append(args[i])
                else:
                    user_list.append(user)

            if len(badUsers) > 0:
                raise commands.BadArgument(
                    f"No user was found for: {','.join(badUsers)}"
                )

        return user_list


# https://github.com/Rapptz/discord.py/blob/master/examples/views/confirm.py
# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(
        self, allowed_respondents: typing.List[discord.Member | discord.User] = []
    ):
        super().__init__()
        self.value = None
        self.allowed_respondents = allowed_respondents
        self.is_limiting_respondents = len(allowed_respondents) > 0
        self.interaction: discord.Interaction = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if (
            self.is_limiting_respondents
            and interaction.user not in self.allowed_respondents
        ):
            await interaction.response.send_message(
                "You aren't qualified to respond to this.", ephemeral=True
            )
            return

        await interaction.response.send_message("Confirming")
        self.interaction = interaction
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (
            self.is_limiting_respondents
            and interaction.user not in self.allowed_respondents
        ):
            await interaction.response.send_message(
                "You aren't qualified to respond to this.", ephemeral=True
            )
            return

        await interaction.response.send_message("Cancelling")
        self.interaction = interaction
        self.value = False
        self.stop()


class Purge(commands.Cog):
    """
    Purges X posts from a selected channel.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )
        pass

    def _file_header(
        self,
        users: typing.List[discord.User],
        channel: discord.TextChannel,
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

    @commands.hybrid_group()
    @commands.admin_or_can_manage_channel()
    async def purge(self, ctx: commands.Context):
        """Purges messages for the given user or channel

        Args:
            ctx (commands.Context): Command context.
        """

    @purge.command()
    @commands.admin_or_can_manage_channel()
    async def channel(
        self,
        ctx: commands.Context,
        number: int,
        channel: typing.Optional[discord.TextChannel],
    ):
        """Deletes up to X messages from the supplied channel (or current channel if none exists).

        Args:
            ctx (commands.Context): Command context.
            number (int): The number of posts to delete.
            channel (typing.Optional[discord.TextChannel]): The channel to delete from.  Defaults to current channel.
        """
        if channel is None:
            channel = ctx.channel

        deferment = await ctx.defer(ephemeral=False)

        messages = channel.history(limit=number, before=ctx.message, oldest_first=False)

        list = []

        async for message in messages:
            list.append(message)

        list.reverse()

        first_deleted_message: discord.Message = list[0]
        last_deleted_message: discord.Message = list[-1]

        number = len(list)

        embed = discord.Embed()
        embed.title = f"Deleting {number} message{'' if number == 1 else 's'}:"
        embed.description = f"Channel: {channel.mention}"
        embed.description += "\n"
        embed.description += f"First Message: {first_deleted_message.jump_url}"
        embed.description += "\n"
        embed.description += f"Last Message: {last_deleted_message.jump_url}"

        view = Confirm(allowed_respondents=[ctx.author])

        prompt = await ctx.send(embed=embed, view=view)

        await view.wait()
        followup = await view.interaction.original_response()

        if view.value is None:
            followup = await ctx.channel.send("Timed out")
            pass
        elif view.value:
            # for i in range(0, len(list), CHUNK_SIZE):
            #     chunk = list[i: i + CHUNK_SIZE]
            await channel.purge(
                limit=number, before=ctx.message, bulk=True, oldest_first=False
            )
            # await view.response.edit(content=f"{i + CHUNK_SIZE if i + CHUNK_SIZE < number else number} out of {number} deleted.")
            # await asyncio.sleep(3)

            followup = await followup.edit(content="Deleted.")
            pass
        else:
            followup - await followup.edit(content=f"Cancelled.")
            pass

        await asyncio.sleep(3)
        await ctx.channel.delete_messages([ctx.message, deferment, prompt, followup])
        pass

    @purge.command()
    @commands.admin_or_can_manage_channel()
    async def user(
        self,
        ctx: commands.Context,
        users: UserParser,
        in_channels: typing.Optional[ChannelParser],
        ignore_channels: typing.Optional[ChannelParser],
        limit: typing.Optional[int],
    ):
        """Purges messages for given users in channels

        Args:
            ctx (commands.Context): Command Context
            users (typing.List[discord.Member]): The list of users to purge.
            inChannels (typing.Optional[typing.List[discord.TextChannel]]): (optional) The channels to screen for.
            ignoreChannels (typing.Optional[typing.List[discord.TextChannel]]): (optional) The channels to not include.
            limit (typing.Optional[int]): (optional) A limit on how many messages to purge.
        """

        if in_channels is None:
            in_channels = ctx.guild.channels

        in_channels = [
            channel
            for channel in in_channels
            if channel.type in TEXT_CHANNEL_TYPES
            and channel.permissions_for(
                ctx.guild.get_member(self.bot.user.id)
            ).read_messages
            and channel.permissions_for(
                ctx.guild.get_member(self.bot.user.id)
            ).read_message_history
            and channel.permissions_for(
                ctx.guild.get_member(self.bot.user.id)
            ).manage_messages
        ]

        if ignore_channels is not None:
            in_channels = [
                channel
                for channel in in_channels
                if channel.id not in [channel.id for channel in ignore_channels]
            ]

        in_channels.sort(key=lambda c: c.position)

        messages = {}
        number = 0

        deferment = await ctx.send("Starting fetch")

        user_ids = [user.id for user in users]

        response = await ctx.channel.send("Fetching...")

        for channel in in_channels:
            await response.edit(content=f"Fetching...{channel.mention}")
            messages[channel.id] = []
            channel_scan_number = 0
            async for message in channel.history(
                limit=None, before=ctx.message, oldest_first=False
            ):
                if message.author.id in user_ids:
                    messages[channel.id].append(message)
                    number += 1
                    channel_scan_number += 1

                    if limit is not None and channel_scan_number >= limit:
                        break

        if number == 0:
            await ctx.channel.delete_messages([response])
            await ctx.send("No messages found.")
            return

        channel_mentions = [channel.mention for channel in in_channels]

        embed = discord.Embed()
        embed.title = f"Deleting {number} message{'' if number == 1 else 's'}:"
        embed.description = f"**User**: {','.join([user.mention for user in users])}"
        embed.description += f"\n"
        embed.description += f"**Channels**: {','.join(channel_mentions)}"
        embed.description += f"\n"
        embed.description += f"**Number**: {number}"

        view = Confirm(allowed_respondents=[ctx.author])

        prompt = await ctx.send(embed=embed, view=view)

        await view.wait()

        if not view.interaction is None:
            followup = await view.interaction.original_response()

        if view.value is None:
            followup = await ctx.channel.send("Timed out")
            pass
        elif view.value:
            completed_channels: typing.List[discord.TextChannel] = []
            current_total = 0
            files = []

            def generate_followup_str(
                channel, channel_current_total, channel_total, current_total
            ) -> str:
                followup_str = f"**Completed**: {','.join([channel.mention for channel in completed_channels])}"
                followup_str += f"\n"
                followup_str += f"**Currently On**: {channel.mention} ({channel_current_total} out of {channel_total})"
                followup_str += f"\n"
                followup_str += f"**Total**: {current_total} out of {number}"
                return followup_str

            for id, messages in messages.items():
                channel = ctx.guild.get_channel(id)
                channel_total = len(messages)
                channel_current_total = 0

                await followup.edit(
                    content=generate_followup_str(
                        channel, channel_current_total, channel_total, current_total
                    )
                )

                if len(messages) > 0:
                    file = self._file_header(users, channel, messages)

                    bulk_messages = [
                        message
                        for message in messages
                        if message.created_at
                        > (
                            datetime.datetime.utcnow() - datetime.timedelta(days=14)
                        ).astimezone(tz=pytz.timezone("UTC"))
                    ]

                    file += "\n".join(
                        [self._file_line(message) for message in bulk_messages]
                    )

                    await channel.delete_messages(bulk_messages)

                    channel_current_total += len(bulk_messages)
                    current_total += len(bulk_messages)

                    remaining_messages = [
                        message for message in messages if message not in bulk_messages
                    ]
                    for message in remaining_messages:
                        try:
                            await message.delete()
                        except Exception as e:
                            print(e)
                            pass
                        channel_current_total += 1
                        current_total += 1
                        await followup.edit(
                            content=generate_followup_str(
                                channel,
                                channel_current_total,
                                channel_total,
                                current_total,
                            )
                        )
                        file += self._file_line(message) + "\n"
                        await asyncio.sleep(3)

                    f = io.StringIO(file)
                    await ctx.author.send(
                        file=discord.File(
                            fp=f,
                            filename=f"{channel.name}_{int(datetime.datetime.now().strftime('%Y%m%d'))}.txt",
                        )
                    )

                completed_channels.append(channel)

            followup = await followup.edit(content="Deleted.")
            pass
        else:
            followup = await followup.edit(content=f"Cancelled.")
            pass

        await asyncio.sleep(3)
        await ctx.channel.delete_messages(
            [ctx.message, deferment, response, prompt, followup]
        )
        pass

        pass
