import asyncio
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.views.confirmation import ConfirmationView

from .config import GuildConfig

REGISTERED_ROLE_TOKEN = "$REGISTERED_ROLES$"
REGISTERED_ROLE_COUNT_TOKEN = "$REGISTERED_ROLE_COUNT$"
ASSIGNED_ROLE_TOKEN = "$ASSIGNED_ROLE$"

DEFAULT_GUILD : GuildConfig = {
    'enabled': True,
    'assigned_role_id': None,
    'registered_role_ids': [],
    'registered_role_count': 3,
    'responses': [
        f"You already have {REGISTERED_ROLE_COUNT_TOKEN} roles: {REGISTERED_ROLE_TOKEN}.  You have been given {ASSIGNED_ROLE_TOKEN}.",
    ]
}

class RoleBlocker(commands.Cog):
    """
    Blocks users from getting a new role if they have pre-existing ones.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    async def __find_users(self, ctx: commands.GuildContext) -> typing.List[discord.Member]:
        registered_role_count = await self.config.guild(ctx.guild).registered_role_count()
        registered_role_ids = await self.config.guild(ctx.guild).registered_role_ids()
        assigned_role_id = await self.config.guild(ctx.guild).assigned_role_id()
        assigned_role = ctx.guild.get_role(assigned_role_id)

        members = []

        for member in ctx.guild.members:
            found_roles = [role for role in member.roles if role.id in registered_role_ids]
            if len(found_roles) >= registered_role_count and (assigned_role is None or assigned_role.id not in [role.id for role in member.roles]):
                members.append(member)

        return members

    async def __convert(self, ctx: commands.GuildContext, members: typing.Optional[typing.Sequence[discord.Member]] = None) -> int:
        registered_role_count = await self.config.guild(ctx.guild).registered_role_count()
        assigned_role_id = await self.config.guild(ctx.guild).assigned_role_id()
        assigned_role = ctx.guild.get_role(assigned_role_id)
        registered_role_ids = await self.config.guild(ctx.guild).registered_role_ids()

        count = 0

        if members is None:
            members = ctx.guild.members

        for member in members:
            found_roles = [role for role in member.roles if role.id in registered_role_ids]
            if len(found_roles) >= registered_role_count:
                if assigned_role is not None and assigned_role.id not in [role.id for role in member.roles]:
                    try:
                        await member.add_roles(assigned_role, reason="Roleblocker assigned role.")
                    except discord.Forbidden:
                        await self.bot.send_to_owners(f"Roleblocker: I do not have permission to add role `{assigned_role_id}` to {member.mention} in {ctx.guild.name}.")

                    count += 1

                if len(found_roles) > registered_role_count:
                    found_roles.sort(key=lambda role: role.created_at)
                    roles_to_be_removed = found_roles[registered_role_count:]
                    try:
                        await member.remove_roles(*roles_to_be_removed, reason="Removing extra registered roles.")
                    except discord.Forbidden:
                        await self.bot.send_to_owners(f"Roleblocker: I do not have permission to remove roles from {member.mention} in {ctx.guild.name}.")

                await asyncio.sleep(1)

        return count

    @commands.group()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def roleblocker(self, ctx: commands.GuildContext):
        """Role blocking commands."""
        pass

    @roleblocker.command()
    @commands.is_owner()
    @commands.guild_only()
    async def role_convert(self, ctx: commands.GuildContext, from_role: discord.Role, to_role: discord.Role):
        """Convert all users with a role to another role."""
        count = 0
        message = await ctx.send(f"Converting users from {from_role.mention} to {to_role.mention}...")

        for member in ctx.guild.members:
            if from_role in member.roles:
                count += 1
                try:
                    await member.remove_roles(from_role, reason="Role conversion.")
                    if to_role not in member.roles:
                        await member.add_roles(to_role, reason="Role conversion.")
                except discord.Forbidden:
                    await self.bot.send_to_owners(f"Roleblocker: I do not have permission to convert roles for {member.mention} in {ctx.guild.name}.")

                await asyncio.sleep(1)

        await message.edit(f"Converted {count} users from {from_role.mention} to {to_role.mention}.")
        pass

    @roleblocker.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def enabled(self, ctx: commands.GuildContext, is_enabled: typing.Optional[bool] = None):
        """Enable or disable role blocking."""
        if is_enabled is None:
            is_enabled = await self.config.guild(ctx.guild).enabled()

        await self.config.guild(ctx.guild).enabled.set(is_enabled)
        await ctx.send(f"Role blocking is {'`ENABLED`' if is_enabled else '`DISABLED`'}.")

    @roleblocker.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def register(self, ctx: commands.GuildContext, roles: commands.Greedy[discord.Role]):
        """Register roles to be counted and blocked."""
        registered_role_ids = await self.config.guild(ctx.guild).registered_role_ids()
        registered_roles = [role for role in ctx.guild.roles if role.id in registered_role_ids]
        registered_roles.extend(role for role in roles)
        registered_roles = list(set(registered_roles))

        await self.config.guild(ctx.guild).registered_role_ids.set([role.id for role in registered_roles])

        await ctx.send(f"Roles registered: {', '.join(role.mention for role in registered_roles)}")

        await self.convertusers(ctx)

    @roleblocker.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def unregister(self, ctx: commands.GuildContext, roles: commands.Greedy[discord.Role]):
        """Unregister roles to be counted and blocked."""
        registered_role_ids = await self.config.guild(ctx.guild).registered_role_ids()
        registered_roles = [role for role in ctx.guild.roles if role.id in registered_role_ids]
        registered_roles = [role for role in registered_roles if role not in roles]

        await self.config.guild(ctx.guild).registered_role_ids.set([role.id for role in registered_roles])

        await ctx.send(f"Roles registered: {', '.join(role.mention for role in registered_roles)}")

    @roleblocker.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def count(self, ctx: commands.GuildContext, count: typing.Optional[int] = None):
        """Set the count of registered roles required to block."""
        if count is None:
            count = await self.config.guild(ctx.guild).registered_role_count()

        await self.config.guild(ctx.guild).registered_role_count.set(count)
        await ctx.send(f"Will block users from trying to acquire registered roles after `{count}` roles have been assigned.")

    @roleblocker.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def assignedrole(self, ctx: commands.GuildContext, role: typing.Optional[discord.Role]):
        """Set the role to assign to users who try to acquire a blocked role."""
        if role is None:
            role = await self.config.guild(ctx.guild).assigned_role_id()

        await self.config.guild(ctx.guild).assigned_role_id.set(role.id)
        await ctx.send(f"Will assign {role.mention} to users after {await self.config.guild(ctx.guild).registered_role_count()} roles have been assigned.")

    @roleblocker.command(aliases=['convert', 'graduate'])
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def convertusers(self, ctx: commands.GuildContext):
        """Convert all users who have more than or equal to the registered role count, giving them the assigned role."""
        view = ConfirmationView(
            author=ctx.author,
        )

        registered_role_count = await self.config.guild(ctx.guild).registered_role_count()

        found_members = await self.__find_users(ctx)

        if len(found_members) == 0:
            await ctx.send("No errant users found.")
            return

        confirmation_message = await ctx.send(f"Would you like to convert `{len(found_members)}` users who have {registered_role_count} or more registered roles?", view=view)

        if not await view.wait() or view.value:
            await confirmation_message.edit(content="Converting users...", view=None)
            count = await self.__convert(ctx, members=found_members)
            await ctx.send(f"{count} users have been converted.")

        await confirmation_message.delete()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot:
            return

        if before.roles == after.roles:
            return
        
        if len(before.roles) >= len(after.roles):
            return

        if not await self.config.guild(before.guild).enabled():
            return

        registered_role_count = await self.config.guild(before.guild).registered_role_count()
        registered_role_ids = await self.config.guild(before.guild).registered_role_ids()

        found_roles = [role for role in after.roles if role.id in registered_role_ids]
        if len(found_roles) > registered_role_count:
            found_roles.sort(key=lambda role: role.created_at)
            roles_to_be_removed = found_roles[registered_role_count:]
            try:
                await after.remove_roles(*roles_to_be_removed, reason="Removing extra registered roles.")
            except discord.Forbidden:
                await self.bot.send_to_owners(f"Roleblocker: I do not have permission to remove roles from {after.mention} in {before.guild.name}.")