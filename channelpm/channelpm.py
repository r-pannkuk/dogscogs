from typing import Literal, Optional
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT = 2048
COG_IDENTIFIER = 260288776360820736

BASECOG = getattr(commands, "Cog", object)
DEF_GLOBAL = {
    "dump_channel": None,
    "reply_target": None
}

DEF_GUILD = {
    "ignored_users": [],
    "dump_channel": None,
    "reply_target": None
}

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class ChannelPM(commands.Cog):
    """
    Messages to the bot will be redirected to a specified channel.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_global(**DEF_GLOBAL)
        self.config.register_guild(**DEF_GUILD)

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
        return

    @commands.group()
    async def channelpm(self, ctx):
        """
        Manages channel PM's.
        """
        pass

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @channelpm.command(usage="<channel>")
    async def channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """
        Sets the channel where communications will be sent.
        """
        if channel is None:
            channel = self.bot.get_channel(await self.config.guild(ctx.guild).dump_channel())

            if channel is None:
                return await ctx.send("PM channel currently not set.")

            return await ctx.send(f"PM channel currently set to {channel.mention}.")

        await self.config.guild(ctx.guild).dump_channel.set(channel.id)
        await ctx.send(f"Done. Set {channel.mention} as the channel for communications.")
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @channelpm.command(usage="<member>")
    async def ignore(self, ctx: commands.Context, member: typing.Union[discord.Member, discord.User]):
        """
        Adds a user to an ignore list for PM replies. 
        """
        ignore_list: list = await self.config.guild(ctx.guild).ignored_users()

        if member.id in ignore_list:
            await ctx.send(f"**{member.display_name}** is already found on this server's ignore list.")
            return

        ignore_list.append(member.id)
        await self.config.guild(ctx.guild).ignored_users.set(ignore_list)

        await ctx.send(f"**{member.display_name}** will now be ignored for all PM's sent to this server.")
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @channelpm.command(usage="<member>")
    async def unignore(self, ctx: commands.Context, member: typing.Union[discord.Member, discord.User]):
        """
        Stops a user from being ignored in channel PM's. 
        """
        ignore_list: list = await self.config.guild(ctx.guild).ignored_users()

        if member.id not in ignore_list:
            await ctx.send(f"**{member.display_name}** was not found on this server's ignore list.")
            return

        ignore_list.remove(member.id)
        await self.config.guild(ctx.guild).ignored_users.set(ignore_list)

        await ctx.send(f"**{member.display_name}** will now be able to send PM's to this server again.")
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @channelpm.command()
    async def ignorelist(self, ctx: commands.Context):
        """
        Displays the list of users ignored on this server. 
        """
        guild: discord.Guild = ctx.guild
        ignore_list: list = await self.config.guild(guild).ignored_users()

        if len(ignore_list) == 0:
            await ctx.send(f"No users are ignored for PM's on this server.")
            return

        member_list: typing.List[typing.Tuple[typing.Union[discord.Member, typing.Any], int]] = [
            (guild.get_member(id), id) for id in ignore_list
        ]

        title = f"Ignore List for {guild.name}:"

        while len(member_list) > 0:
            description = ""

            while len(member_list) > 0:
                tuple = member_list[0]
                member: discord.Member = tuple[0]

                if member is None:
                    member = self.bot.get_user(tuple[1])
                    string = f"{member.mention} - User not found on server.\n"
                else:
                    string = f"{member.mention}\n"
                
                if len(description) + len(string) > DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT:
                    break

                description += string

                member_list.pop(0)

            if len(description) == 0:
                await ctx.send(f"Something went wrong.")
                await self.bot.send_to_owners(f"""`channelpm: Failed to generate ignore list.
                -- guild: {guild.name} <{guild.id}>
                -- ignore_list: {ignore_list}`""")
                return

            embed = discord.Embed(
                title=title,
                description=description
            )

            title = ""

            await ctx.send(embed=embed)
        return

    async def message(self, ctx: commands.Context, user: typing.Union[discord.Member, discord.User], *, message: str = "", anonymous: bool = False):
        """Messages a user directly via mod channel.

        __Args__:
            ctx (commands.Context): The command context.
            user (typing.Union[discord.Member, discord.User]): The user for messaging.
            message (str): Message to send the user over DM.
            anonymous (bool): Whether or not to send the message anonymously.
        """
        if ctx.author == self.bot.user:
            return

        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return

        response_channel = self.bot.get_channel(await self.config.guild(ctx.guild).dump_channel())

        if response_channel is None:
            await self.config.guild(ctx.guild).dump_channel.set(ctx.channel.id)

        member : discord.Member = ctx.guild.get_member(user.id)

        if member is None:
            name = f"{user.name}#{user.discriminator}"
        else:
            name = f"{member.display_name}"

        
        if anonymous:
            await user.send(f"`[{ctx.guild.name}]`**>{name}**: {message}")
            await ctx.channel.send(f"**{ctx.author.display_name} (anon)>{name}**: {message}")
        else:
            await user.send(f"`[{ctx.guild.name}]`**{ctx.author.display_name}>{name}**: {message}")
            await ctx.channel.send(f"**{ctx.author.display_name}>{name}**: {message}")

        await ctx.message.delete()
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.command(usage="<user> <message>", rest_is_raw=True, aliases=["message", "msg"])
    async def pm(self, ctx: commands.Context, user: typing.Union[discord.Member, discord.User], *, message: str):
        """
        Mesages a user indirectly via the bot.
        """
        await self.message(ctx, user, message=message, anonymous=False)
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.command(usage="<message>", rest_is_raw=True, aliases=["reply"])
    async def r(self, ctx: commands.Context, *, message: str):
        """
        Replies to the last person who messaged the bot.
        """
        await self.pm(ctx, self.bot.get_user(await self.config.guild(ctx.guild).reply_target()), message=message)
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.command(usage="<user> <message>", rest_is_raw=True, aliases=["messageanon", "msganon", "msga"])
    async def pma(self, ctx: commands.Context, user: typing.Union[discord.Member, discord.User], *, message: str):
        """
        Mesages a user indirectly via the bot, anonymously.
        """
        await self.message(ctx, user, message=message, anonymous=True)
        return

    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.command(usage="<user> <message>", rest_is_raw=True, aliases=["replyanon"])
    async def ra(self, ctx: commands.Context, *, message: str):
        """
        Replies to the last person who messaged the bot, anonymously.
        """
        await self.pma(ctx, self.bot.get_user(await self.config.guild(ctx.guild).reply_target()), message=message)
        return

    @commands.dm_only()
    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listens for private messages to forward to the dump channel.
        """
        if not message.channel.type == discord.ChannelType.private:
            return

        if message.author == self.bot.user:
            return

        if message.content.startswith(tuple(await self.bot.get_valid_prefixes())) is True:
            return

        # Find all guilds the user is part of.
        guilds_in : typing.List[discord.Guild] = filter(lambda g: g.get_member(
            message.author.id) != None, self.bot.guilds)

        for guild in guilds_in:
            channel = self.bot.get_channel(await self.config.guild(guild).dump_channel())

            if channel is None:
                continue

            if message.author.id in await self.config.guild(guild).ignored_users():
                # To-Do: Add the user's message to some log for fetching here.
                continue

            await self.config.guild(guild).reply_target.set(message.author.id)

            member : discord.Member = guild.get_member(message.author.id)

            private_message = ""

            if member is None:
                member = message.author
                private_message = f"**{message.author.name}#{message.author.discriminator}** : "
            else:
                private_message = f"**{member.display_name}** ({message.author.name}#{message.author.discriminator}) : "

            private_message += message.content

            await channel.send(private_message)
        return
