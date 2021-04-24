from typing import Literal

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

USERNAME_TOKEN = """%%user%%"""

DEFAULT_MEMBER = {
    "is_gulaged": False,
    "restore_role_ids": None,
    "gulag_channel_id": None,
    "gulag_role_id": None
}

DEFAULT_GUILD = {
    "category_id": None,
    "category_creation_reason": "Warnings channel for moderation of users.",
    "category_name": "Warnings",
    "channel_name": """warning-{0}""".format(USERNAME_TOKEN),
    "gulag_reason": "User being moderated.",
    "permitted_role_ids": [],
    "role_name": """Warned-{0}""".format(USERNAME_TOKEN)
}


class Gulag(commands.Cog):
    """
    Sends a user to a private channel for moderation.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_member(**DEFAULT_MEMBER)

        self.config.register_guild(**DEFAULT_GUILD)

        pass

    async def create_category_channel(self, guild: discord.Guild):
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
                    reason=await self.config.guild(guild).category_creation_reason()
                )

            await self.config.guild(guild).category_id.set(category.id)

        # Gives access to view for all permitted roles.
        for r in await self.config.guild(guild).permitted_roles():
            await category.set_permissions(target=r, overwrite=discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                view_channel=True
            ))

        # Adds default role invisibility.
        await category.set_permissions(target=guild.default_role, overwrite=discord.PermissionOverwrite(
            read_messages=False,
            send_messages=False,
            view_channel=False
        ))

        pass

    async def create_gulag_channel(self, guild: discord.Guild, member: discord.Member) -> discord.TextChannel:
        if guild == None:
            guild = member.guild

        category: discord.CategoryChannel = guild.get_channel(await self.config.guild(guild).category_id())

        if category == None:
            await self.create_category_channel(guild)

        channel_name = (await self.config.guild(guild).channel_name()).replace(
            USERNAME_TOKEN, member.display_name
        )

        return await guild.create_text_channel(
            category=category,
            name=channel_name
        )

    async def create_gulag_role(self, guild: discord.Guild, member: discord.Member, channel: discord.TextChannel) -> discord.Role:
        if guild == None:
            guild = member.guild

        role_name = (await self.config.guild(guild).role_name()).replace(
            USERNAME_TOKEN, member.display_name
        )

        role = await guild.create_role(
            name=role_name,
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

        # Overwrite permissions for this specific role for communication.
        await channel.set_permissions(target=role, overwrite=discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            view_channel=True
        ))

        return role

    @commands.mod()
    @commands.group(invoke_without_command=True, usage="<user>")
    async def gulag(self, ctx: commands.Context, user: discord.User):
        """
        Moderates a user, preventing them from seeing any channels except their own warning channel.
        """
        guild: discord.Guild = ctx.guild

        member: discord.Member = guild.get_member(user.id)

        group = self.config.member_from_ids(guild.id, user.id)

        if group == None or await group.is_gulaged():
            channel = guild.get_channel(await group.gulag_channel_id())

            await ctx.channel.send("""{0} is already gulaged. See: {1}""".format(
                member.display_name,
                channel.mention
            ))
            return

        await self.create_category_channel(guild)

        channel = await self.create_gulag_channel(guild, member)

        gulag_role = await self.create_gulag_role(guild, member, channel)

        current_roles = [r for r in member.roles if r != guild.default_role]

        await group.is_gulaged.set(True)
        await group.restore_role_ids.set([r.id for r in current_roles])
        await group.gulag_channel_id.set(channel.id)
        await group.gulag_role_id.set(gulag_role.id)

        for role in current_roles:
            await member.remove_roles(role,
                                      atomic=True,
                                      reason=await self.config.guild(guild).gulag_reason())

        await member.add_roles(gulag_role,
                               atomic=True,
                               reason=await self.config.guild(guild).gulag_reason())

        await ctx.channel.send("""{0} has been moderated. See: {1}""".format(
            member.display_name, channel.mention))

    @commands.mod()
    @commands.command(usage="<user>")
    async def ungulag(self, ctx: commands.Context, user: discord.User):
        """
        Unmoderates a user, restoring all roles they had and cleaning up any moderation roles or channels created.
        """
        guild: discord.Guild = ctx.guild

        member: discord.Member = guild.get_member(user.id)

        group = self.config.member_from_ids(guild.id, user.id)

        if group == None or not await group.is_gulaged():
            await ctx.channel.send(
                """{0} is not currently gulaged.""".format(member.display_name))
            return

        channel: discord.TextChannel = guild.get_channel(
            await group.gulag_channel_id()
        )

        if channel != None:
            await channel.delete()

        role: discord.Role = guild.get_role(await group.gulag_role_id())

        if role != None:
            await role.delete()

        for r in await group.restore_role_ids():
            role = guild.get_role(r)

            if role != None or role == guild.default_role:
                await member.add_roles(role, atomic=True)

        await group.is_gulaged.set(False)
        await group.restore_role_ids.set(None)
        await group.gulag_channel_id.set(None)
        await group.gulag_role_id.set(None)

        if ctx.channel.id != channel.id:
            await ctx.channel.send(
                """{0} has been unmoderated.""".format(member.display_name)
            )

    @commands.mod()
    @gulag.command(usage="<role>")
    async def add_mod_role(self, ctx: commands.Context, role: discord.Role):
        """
        Adds a mod role to the list of roles with permissions to view moderation channels.
        """
        roles: list[int] = await self.config.guild(ctx.guild).permitted_role_ids()

        if role.id in roles:
            await ctx.channel.send("""Role {0} is already set to view moderation channels.""".format(role.name))
            return

        roles.append(role.id)

        await self.config.guild(ctx.guild).permitted_role_ids.set(roles)

        await ctx.channel.send("""Role {0} can now view moderation channels.""".format(role.name))
        return


    @commands.mod()
    @gulag.command(usage="<role>")
    async def remove_mod_role(self, ctx: commands.Context, role: discord.Role):
        """
        Adds a mod role to the list of roles with permissions to view moderation channels.
        """
        roles: list[int] = await self.config.guild(ctx.guild).permitted_role_ids()

        if role.id not in roles:
            await ctx.channel.send("""Role {0} is not set to view moderation channels.""".format(role.name))
            return

        roles.remove(role.id)

        await self.config.guild(ctx.guild).permitted_role_ids.set(roles)

        await ctx.channel.send("""Role {0} will no longer be able to view moderation channels.""".format(role.name))
        return


    @commands.mod()
    @gulag.command(usage="<user>")
    async def delete_data_for_user(self, ctx: commands.Context, user: discord.User):
        """
        Deletes stored data for a user.  Only use if you know what you're doing!
        """
        await self.config.user(user).clear()
        await self.config.member_from_ids(ctx.guild.id, user.id).clear()
        # self.red_delete_data_for_user(self, requester=ctx.author, user_id=user.id)

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
