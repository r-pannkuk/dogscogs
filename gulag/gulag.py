from datetime import datetime
from typing import Literal
import typing
import pytz

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT = 2048
DISCORD_MAX_MESSAGE_SIZE_LIMIT = 2000
COG_IDENTIFIER = 260288776360820736

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

USERNAME_TOKEN = "%%user%%"

DEFAULT_MEMBER = {
    "is_gulaged": False,
    "is_privileged": False,
    "restore_role_ids": None,
    "restricted_date": None,
    "gulag_channel_id": None,
    "gulag_role_id": None
}

DEFAULT_ROLE = {
    "is_gulag_role": False,
    "is_privileged": False,
    "is_bot_created": False
}

DEFAULT_CHANNEL = {
    "is_gulag_channel": False,
    "user_id": None
}

DEFAULT_GUILD = {
    "category_id": None,
    "category_creation_reason": "Warnings channel for moderation of users.",
    "category_name": "Moderation",
    "channel_name": f"warning-{USERNAME_TOKEN}",
    "gulag_reason": "User being moderated.",
    "gulag_role_id": None,
    "gulag_role_name": f"Warnings",
    "log_channel_id": None,
    "log_channel_name": "gulogs",
    "logs_enabled": True
}


class Gulag(commands.Cog):
    """
    Sends a user to a private channel for moderation.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_member(**DEFAULT_MEMBER)

        self.config.register_guild(**DEFAULT_GUILD)

        self.config.register_role(**DEFAULT_ROLE)

        self.config.register_channel(**DEFAULT_CHANNEL)

        pass

    async def create_category_channel(self, guild: discord.Guild):
        """
        Creates a category channel for inserting moderation channels into.
        """
        channel_id = await self.config.guild(guild).category_id()

        category: discord.CategoryChannel = guild.get_channel(channel_id)

        if category == None:

            category_name = await self.config.guild(guild).category_name()

            category: discord.CategoryChannel = next((
                cat for cat in guild.categories if cat.name == category_name
            ), None)

            if category == None:
                category = await guild.create_category(
                    name=await self.config.guild(guild).category_name(),
                    position=len(guild.categories),
                    reason=await self.config.guild(guild).category_creation_reason(),
                )

            await self.config.guild(guild).category_id.set(category.id)

        # # Gives access to view for all permitted roles.
        # for role in guild.roles:
        #     if await self.config.role(role).is_privileged():
        #         await category.set_permissions(target=role, overwrite=discord.PermissionOverwrite(
        #             read_messages=True,
        #             send_messages=True,
        #             view_channel=True
        #         ))

        # # Adds default role invisibility.
        # await category.set_permissions(target=guild.default_role, overwrite=discord.PermissionOverwrite(
        #     read_messages=False,
        #     send_messages=False,
        #     view_channel=False
        # ))

        return category

    async def create_gulag_channel(self, guild: discord.Guild, member: discord.Member) -> discord.TextChannel:
        """
        Creates a new moderation channel that a user will be able to post in when moderated.
        """
        if guild == None:
            guild = member.guild

        category: discord.CategoryChannel = guild.get_channel(await self.config.guild(guild).category_id())

        if category == None:
            await self.create_category_channel(guild)

        channel_name = (await self.config.guild(guild).channel_name()).replace(
            USERNAME_TOKEN, member.display_name
        )

        channel = await guild.create_text_channel(
            category=category,
            name=channel_name,
        )

        await channel.set_permissions(guild.me,
                                      read_messages=True,
                                      send_messages=True,
                                      manage_channels=True)

        await self.config.channel(channel).is_gulag_channel.set(True)
        await self.config.channel(channel).user_id.set(member.id)

        return channel

    async def create_gulag_role(self, guild, name):
        """
        Creates a new role for gulaging with the appropriate permissions.
        """
        role = await guild.create_role(
            name=name,
            mentionable=False,
            hoist=False,
            permissions=discord.Permissions.none()
        )

        for channel in guild.channels:
            await channel.set_permissions(target=role, overwrite=discord.PermissionOverwrite(
                read_messages=False,
                send_messages=False,
                view_channel=False
            ))

        await self.config.role(role).is_bot_created.set(True)
        await self.config.role(role).is_gulag_role.set(True)
        await self.config.guild(guild).gulag_role_id.set(role.id)
        return role

    async def moderate_user(self,
                            member: discord.Member,
                            gulag_channel: typing.Optional[discord.TextChannel] = None,
                            gulag_role: typing.Optional[discord.Role] = None
                            ):
        """
        Flags and sets a user for moderation.
        """
        guild: discord.Guild = member.guild

        group = self.config.member(member)

        if gulag_channel is None:
            gulag_channel = guild.get_channel(await self.config.member(member).gulag_channel_id())

            if gulag_channel is None:
                await self.create_category_channel(guild)
                gulag_channel = await self.create_gulag_channel(guild, member)

        if gulag_role is None:
            gulag_role: discord.Role = guild.get_role(await self.config.member(member).gulag_role_id())

            if gulag_role is None:
                # gulag_role = await self.create_gulag_role(guild, member, gulag_channel)
                gulag_role = guild.get_role(await self.config.guild(guild).gulag_role_id())

                if gulag_role is None:
                    gulag_role = await self.create_gulag_role(guild, await self.config.guild(guild).gulag_role_name())

        existing_restoration_roles = await group.restore_role_ids() or list()
        restricted_date = await group.restricted_date()
        current_roles = [r for r in member.roles if r != guild.default_role] + \
            [guild.get_role(id) for id in existing_restoration_roles]

        # Overwrite permissions for this specific role for communication.
        await gulag_channel.set_permissions(target=member, overwrite=discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            view_channel=True
        ))

        await group.is_gulaged.set(True)
        await group.restore_role_ids.set([r.id for r in current_roles])
        await group.gulag_channel_id.set(gulag_channel.id)
        await group.restricted_date.set(restricted_date or datetime.now().timestamp())
        await group.gulag_role_id.set(gulag_role.id)

        for role in current_roles:
            try:
                await member.remove_roles(role,
                                        atomic=True,
                                        reason=await self.config.guild(guild).gulag_reason())
            except:
                print(f"Couldn't remove role {role.name}")
                pass

        await member.add_roles(gulag_role,
                               atomic=True,
                               reason=await self.config.guild(guild).gulag_reason())

        await self.config.channel(gulag_channel).is_gulag_channel.set(True)
        pass

    async def unmoderate_user(self,
                              member: discord.Member,
                              gulag_channel: typing.Optional[discord.TextChannel] = None,
                              gulag_role: typing.Optional[discord.Role] = None
                              ):
        """
        Flags and sets a user to remove moderation.
        """
        guild: discord.Guild = member.guild
        group = self.config.member(member)

        # DUMB LOGGING THING THAT SHOULD BE AN EVENT
        logs_enabled: bool = await self.config.guild(guild).logs_enabled()
        log_channel: discord.TextChannel = guild.get_channel(await self.config.guild(guild).log_channel_id())

        if gulag_channel is None:
            gulag_channel: discord.TextChannel = guild.get_channel(await self.config.member(member).gulag_channel_id())

        if gulag_role is None:
            gulag_role: discord.Role = guild.get_role(await self.config.member(member).gulag_role_id())

        if logs_enabled and log_channel is not None and gulag_channel is not None:

            messages: list[discord.Message] = [message async for message in gulag_channel.history(limit=200)]
            log = ''

            if len(messages) > 0:
                messages.sort(key=lambda m: m.created_at)
                log = f'__Chat History of **{gulag_channel.name}**__:\n'

            for message in messages:
                author: discord.Member = message.author
                time = datetime(
                    year=message.created_at.year,
                    month=message.created_at.month,
                    day=message.created_at.day,
                    hour=message.created_at.hour,
                    minute=message.created_at.minute,
                    second=message.created_at.second,
                    tzinfo=pytz.timezone("UTC")
                )
                time = time.astimezone(pytz.timezone("US/Eastern"))
                timestring = time.strftime("%m/%d/%Y %I:%M:%S %p")
                str = f"`{timestring}` **{author.display_name}**: "

                if len(message.clean_content) < DISCORD_MAX_MESSAGE_SIZE_LIMIT-100:
                    str += f"{message.clean_content}\n"
                else:
                    str += f"{message.clean_content[:DISCORD_MAX_MESSAGE_SIZE_LIMIT-100]}...\n"

                for attachment in message.attachments:
                    str += attachment.url + '\n'

                if len(log) + len(str) > DISCORD_MAX_MESSAGE_SIZE_LIMIT:
                    try:
                        await log_channel.send(log)
                    except:
                        print(f"Couldn't send to channel: {log_channel.name}")
                        break
                    log = str
                else:
                    log += str

            if len(log) > 0:
                try:
                    await log_channel.send(log)
                except Exception as e:
                    print(f"Couldn't send to channel: {log_channel.name}")
                    print(e)
        # END OF DUMB LOGGING THING THAT SHOULD BE AN EVENT

        restore_role_ids = await group.restore_role_ids()

        await group.is_gulaged.set(False)
        await group.restore_role_ids.set(None)
        await group.gulag_channel_id.set(None)
        await group.gulag_role_id.set(None)
        await group.restricted_date.set(None)

        if gulag_channel != None:
            await gulag_channel.delete()

        if gulag_role != None:
            await member.remove_roles(gulag_role, atomic=True)

        for r in restore_role_ids:
            role = guild.get_role(r)

            if role != None or role == guild.default_role:
                try:
                    await member.add_roles(role, atomic=True)
                except:
                    print(f"Couldn't add role {role.name}")
                    pass
        pass

    @commands.mod_or_permissions(manage_roles=True)
    @commands.command(usage="<user>", aliases=["moderate"], show_aliases=True)
    async def restrict(self, ctx: commands.Context, *, member: discord.Member):
        """
        Moderates a user, preventing them from seeing any channels except their own warning channel.
        """
        guild: discord.Guild = ctx.guild

        group = self.config.member_from_ids(guild.id, member.id)

        if group == None or await group.is_gulaged():
            gulag_channel = guild.get_channel(await group.gulag_channel_id())

            await ctx.channel.send(f"{member.display_name} is already gulaged. See: {gulag_channel.mention}")
            return

        await self.moderate_user(member)

        self.bot.dispatch("gulag_restrict_member", member)

        gulag_channel: discord.TextChannel = guild.get_channel(await self.config.member(member).gulag_channel_id())

        await ctx.channel.send(f"{member.display_name} has been moderated. See: {gulag_channel.mention}")

    @commands.mod_or_permissions(manage_roles=True)
    @commands.command(usage="<user>", aliases=["unmoderate"], show_aliases=True)
    async def unrestrict(self, ctx: commands.Context, *, member: discord.Member):
        """
        Unmoderates a user, restoring all roles they had and cleaning up any moderation roles or channels created.
        """
        guild: discord.Guild = ctx.guild

        group = self.config.member_from_ids(guild.id, member.id)

        if group == None or not await group.is_gulaged():
            await ctx.channel.send(f"{member.display_name} is not currently gulaged.")
            return

        self.bot.dispatch("gulag_unrestrict_member", member)

        await self.unmoderate_user(member)

        if ctx.channel.id in [channel.id for channel in guild.channels]:
            await ctx.channel.send(f"{member.display_name} has been unmoderated.")

    @commands.mod_or_permissions(manage_roles=True)
    @commands.group()
    async def gulag(self, ctx: commands.Context):
        """
        Settings for the gulag cog.
        """
        pass

    @commands.mod_or_permissions(manage_roles=True)
    @ gulag.command(usage="<user|role>", aliases=["allow"], show_aliases=True)
    async def permit(self, ctx: commands.Context, *, target: typing.Union[discord.Member, discord.Role]):
        """
        Allows a user or role to view moderation channels.
        """
        group = None
        if isinstance(target, discord.Member):
            group = self.config.member(target)
            name = target.display_name
        if isinstance(target, discord.Role):
            group = self.config.role(target)
            name = f"Role {target.name}"

        if await group.is_privileged():
            await ctx.channel.send(f"{name} is already set to view moderation channels.")
            return

        guild: discord.Guild = target.guild
        log_channel_id = await self.config.guild(guild).log_channel_id()

        for channel in guild.channels:
            if await self.config.channel(channel).is_gulag_channel() or channel.id == log_channel_id:
                await channel.set_permissions(target=target, overwrite=discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    view_channel=True
                ))

        await group.is_privileged.set(True)

        await ctx.channel.send(f"{name} is now set to view moderation channels.")
        return

    @commands.mod_or_permissions(manage_roles=True)
    @ gulag.command(usage="<user|role>", aliases=["disallow", "unpermit"], show_aliases=True)
    async def prohibit(self, ctx: commands.Context, *, target: typing.Union[discord.Member, discord.Role]):
        """
        Prohibits a user or role from viewing moderation channels.
        """
        group = None
        if isinstance(target, discord.Member):
            group = self.config.member(target)
            name = target.display_name
        if isinstance(target, discord.Role):
            group = self.config.role(target)
            name = f"Role {target.name}"

        if not await group.is_privileged():
            await ctx.channel.send(f"{name} is not set to view moderation channels.")
            return

        guild: discord.Guild = target.guild
        log_channel_id = await self.config.guild(guild).log_channel_id()

        for channel in guild.channels:
            if await self.config.channel(channel).is_gulag_channel() or channel.id == log_channel_id:
                await channel.set_permissions(target=target, overwrite=discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    view_channel=False
                ))

        await group.is_privileged.set(False)
        await ctx.channel.send(f"{name} will no longer be able to view moderation channels.")
        return

    @ commands.mod_or_permissions(manage_roles=True)
    @ gulag.command()
    async def list(self, ctx: commands.Context):
        """
        Displays a list of all users currently being restricted.
        """
        guild: discord.Guild = ctx.guild
        member_list: typing.List[typing.Tuple[
            discord.Member,
            float,
            discord.Role,
            discord.TextChannel
        ]] = []

        gulaged_members = [member for member in guild.members if await self.config.member(member).is_gulaged()]

        for member in gulaged_members:
            timestamp = await self.config.member(member).restricted_date()
            date = datetime.fromtimestamp(timestamp)
            role = guild.get_role(await self.config.member(member).gulag_role_id())
            channel = guild.get_channel(await self.config.member(member).gulag_channel_id())
            member_list.append((member, date, role, channel))

        if len(member_list) == 0:
            await ctx.send(f"No users are being restricted on this server.")
            return

        title = f"Restricted List for {guild.name}:"

        while len(member_list) > 0:
            description = ""

            while len(member_list) > 0:
                tuple = member_list[0]
                member = tuple[0]
                date = tuple[1].astimezone(
                    tz=pytz.timezone("US/Eastern")).date()
                role = tuple[2] or f"**ROLE NOT FOUND**"
                channel = tuple[3] or f"**CHANNEL NOT FOUND**"

                string = f"{member.mention} [{channel.mention}] since {date}\n"

                if len(description) + len(string) > DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT:
                    break

                description += string

                member_list.pop(0)

            if len(description) == 0:
                await ctx.send(f"Something went wrong.")
                await self.bot.send_to_owners(f"""`channelpm: Failed to generate ignore list.
                -- guild: {guild.name} <{guild.id}>
                -- ignore_list: {member_list}`""")
                return

            embed = discord.Embed(
                title=title,
                description=description
            )

            title = ""

            await ctx.send(embed=embed)
        return

    @commands.mod_or_permissions(manage_roles=True)
    @gulag.command(usage="[category]")
    async def category(self, ctx: commands.Context, *, category: typing.Optional[typing.Union[discord.CategoryChannel, str]]):
        """
        Sets or displays the current category channel used for warnings.
        """
        guild: discord.Guild = ctx.guild
        category_id: str = await self.config.guild_from_id(guild.id).category_id()
        old_category: discord.CategoryChannel = guild.get_channel(category_id)

        if category is None:
            if old_category is None:
                await ctx.channel.send(f'Category channel is not currently set.  Please specify a category name.')
            else:
                await ctx.channel.send(f'Category channel is currently set to **{old_category.mention}**.')
            return

        if isinstance(category, str):
            matching_categories: typing.List[discord.CategoryChannel] = [
                cat for cat in guild.categories if str.lower(cat.name) == str.lower(category)]

            if len(matching_categories) > 0:
                category = matching_categories[0]
            else:
                await self.config.guild(guild).category_name.set(category)
                await self.config.guild(guild).category_id.set(None)
                category = await self.create_category_channel(guild)
        elif isinstance(category, discord.CategoryChannel):
            await self.config.guild(guild).category_id.set(category.id)

        log_channel_id = await self.config.guild(guild).log_channel_id()

        for channel in guild.channels:
            if channel.id == log_channel_id or await self.config.channel(channel).is_gulag_channel():
                await channel.edit(category=category)

        if old_category is not None and len(old_category.channels) == 0:
            await old_category.delete()

        await ctx.channel.send(f'Category channel is now set to **{category.mention}**.')
        return

    @ commands.mod_or_permissions(manage_roles=True)
    @ gulag.command()
    async def role(self, ctx: commands.Context):
        """
        Displays the global role in use.
        """
        guild: discord.Guild = ctx.guild
        global_role_id: str = await self.config.guild_from_id(guild.id).gulag_role_id()
        global_role: discord.Role = None

        if global_role_id is not None:
            global_role = guild.get_role(global_role_id)

        prefix = await ctx.bot.get_prefix(ctx.message)

        if isinstance(prefix, list):
            prefix = prefix[0]

        if global_role is None:
            await ctx.channel.send(f'Gulag global role is not currently set.  Please use the `{prefix}gulag setrole` command to create a new gulag role.')
        else:
            await ctx.channel.send(f'Gulag global role is currently set to {global_role.mention}.')
        return

    @ commands.mod_or_permissions(manage_roles=True)
    @ gulag.command(usage="[name]", name="setrole")
    async def set_role(self, ctx: commands.Context, *, target: typing.Optional[typing.Union[discord.Role, str, int]]):
        """
        Sets or creates a global role that will be used to moderate users.
        """
        guild: discord.Guild = ctx.guild

        old_role_id = await self.config.guild_from_id(guild.id).gulag_role_id()

        if target is None:
            name: str = await self.config.guild_from_id(guild.id).gulag_role_name()
            target = name
        elif isinstance(target, discord.Role):
            name = target.name
        elif isinstance(target, int):
            found_role: discord.Role = guild.get_role(int(target))
            if found_role is not None:
                name = found_role.name
                target = found_role
            else:
                name = target
        elif isinstance(target, str):
            name = target

        if old_role_id is not None:
            old_role: discord.Role = guild.get_role(old_role_id)

            if old_role is not None:

                if await self.config.role(old_role).is_bot_created() and old_role.name != name:
                    await old_role.delete(reason="New gulag role is being set, and this was created by the bot.")
                else:
                    await self.config.role(old_role).is_gulag_role.set(False)

        if isinstance(target, str):
            roles: typing.List[discord.Role] = [
                role for role in guild.roles if str.lower(role.name) == str.lower(name)
            ]

            if len(roles) > 0:
                target: discord.Role = roles.pop(0)
            else:
                target: discord.Role = await self.create_gulag_role(guild, target)

        await self.config.role(target).is_gulag_role.set(True)
        await self.config.guild(guild).gulag_role_id.set(target.id)

        await self.config.guild(guild).gulag_role_name.set(name)
        await ctx.channel.send(f"Role {target.mention} will now moderate users.")

        return

    @ commands.mod_or_permissions(manage_roles=True)
    @ gulag.group()
    async def logs(self, ctx: commands.Context):
        """
        Settings for gulag logging.
        """
        pass

    @ commands.mod_or_permissions(manage_roles=True)
    @ logs.command(usage="<channel>")
    async def channel(self, ctx: commands.Context, *, channel: typing.Optional[typing.Union[discord.TextChannel, str]]):
        """
        Sets or displays the channel in use for logging.
        """
        guild: discord.Guild = ctx.guild
        log_channel_id: str = await self.config.guild_from_id(guild.id).log_channel_id()
        log_channel: discord.TextChannel = None

        if log_channel_id is not None:
            log_channel = guild.get_channel(log_channel_id)

        if channel is None:

            if log_channel is None:
                await ctx.channel.send(f'Gulag logs channel is not currently set.  Please specify a channel name.')
            else:
                await ctx.channel.send(f'Gulag logs channel is currently set to {log_channel.mention}.')

            return

        if log_channel and log_channel.id == channel.id:
            await ctx.channel.send(f'Gulag logs channel is already set to {channel.mention}.')
            return

        await self.config.guild_from_id(guild.id).log_channel_id.set(channel.id)

        await ctx.channel.send(f'Gulag logs channel is now set to {channel.mention}.')
        return

    @ commands.mod_or_permissions(manage_roles=True)
    @ logs.command(usage="<name>", name="create")
    async def create_logs(self, ctx: commands.Context, *, name: typing.Optional[str]):
        """
        Creates a new channel to store a history of gulag messages within.
        """
        guild: discord.Guild = ctx.guild

        if name is None:
            name = await self.config.guild_from_id(guild.id).log_channel_name()

        channels: typing.List[discord.Guild] = [
            channel for channel in guild.channels if channel.name == name]

        if len(channels) > 0:
            await ctx.channel.send(f"Already found existing channel with name {channels[0].mention}. Please use a different name.")
            return

        channel = await guild.create_text_channel(
            name=name,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    view_channel=False
                )
            },
            category=guild.get_channel(await self.config.guild(guild).category_id())
        )

        await self.config.guild_from_id(guild.id).log_channel_id.set(channel.id)

        await ctx.channel.send(f"New channel {channel.mention} created. Message logs will be stored.")
        return

    @ logs.command(usage="<True|False>")
    @ commands.mod_or_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """
        Sets whether or not gulag histories are logged.
        """
        guild: discord.Guild = ctx.guild
        logs_enabled = await self.config.guild_from_id(guild.id).logs_enabled()

        log_channel_id = await self.config.guild_from_id(guild.id).log_channel_id()
        prefix = await ctx.bot.get_prefix(ctx.message)

        if isinstance(prefix, list):
            prefix = prefix[0]

        channel_unset_message = f'Please set a logging channel using `{prefix}gulag logs channel <channel>` or create one with `{prefix}gulag logs create <name>`.'

        if log_channel_id is not None:
            log_channel = guild.get_channel(log_channel_id)
            channel_set_message = f"Gulag logs will be displayed in {log_channel.mention}."

        if bool is None:
            status = "**ENABLED**" if logs_enabled else "**DISABLED**"
            if logs_enabled:
                if log_channel_id is None:
                    status += f".  {channel_unset_message}"
                else:
                    status += f".  {channel_set_message}"
            await ctx.channel.send(f"Gulag logging is currently {status}")
            return

        await self.config.guild_from_id(guild.id).logs_enabled.set(bool)

        if bool:
            str = f"Now recording histories of gulag channels."
            log_channel_id = await self.config.guild_from_id(guild.id).log_channel_id()

            if log_channel_id is None:
                str += f" {channel_unset_message}"
            else:
                str += f"  {channel_set_message}"

            await ctx.channel.send(str)
        else:
            await ctx.channel.send(f"No longer recording histories of gulag channels.")
        return

    @ logs.command()
    @ commands.mod_or_permissions(manage_roles=True)
    async def enable(self, ctx: commands.Context):
        """
        Enables gulag logging for this server.
        """
        await self.enabled(ctx, True)
        return

    @ logs.command()
    @ commands.mod_or_permissions(manage_roles=True)
    async def disable(self, ctx: commands.Context):
        """
        Disables logging for this server.
        """
        await self.enabled(ctx, False)
        return

    @ commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        Cleanup
        """
        if await self.config.channel(channel).is_gulag_channel():
            member: discord.Member = channel.guild.get_member(await self.config.channel(channel).user_id())

            if await self.config.member(member).is_gulaged():
                # Specifically not passing channel here because the channel is already in a deleted state.
                await self.unmoderate_user(member)
            return

        if channel.id == await self.config.guild(channel.guild).log_channel_id():
            await self.config.guild(channel.guild).log_channel_id.set(None)
        pass

    @ commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Cleanup
        """
        if len(before.roles) < len(after.roles):
            new_role = next(
                role for role in after.roles if role not in before.roles)

            if await self.config.role(new_role).is_gulag_role():
                if not await self.config.member(before).is_gulaged():
                    await self.moderate_user(before, gulag_role=new_role)
                pass

            pass
        elif len(before.roles) > len(after.roles):
            removed_role = next(
                role for role in before.roles if role not in after.roles)

            if await self.config.role(removed_role).is_gulag_role():
                if await self.config.member(before).is_gulaged():
                    await self.unmoderate_user(before, gulag_role=removed_role)
                pass
            pass
        pass

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Restore status.
        """
        guild: discord.Guild = member.guild

        if await self.config.member(member).is_gulaged():
            gulag_role_id = await self.config.guild(guild).gulag_role_id()
            gulag_role: discord.Role = guild.get_role(gulag_role_id)

            if gulag_role is None:
                return

            gulag_channel_id = await self.config.member(member).gulag_channel_id()
            gulag_channel: discord.TextChannel = guild.get_channel(
                gulag_channel_id)

            if gulag_channel is None:
                return

            await self.moderate_user(member, gulag_role=gulag_role, gulag_channel=gulag_channel)
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """
        Attempting to understand this.
        """
        pass
