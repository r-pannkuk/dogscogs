import asyncio
from typing import Literal

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.views.confirmation import ConfirmationView


RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class RoleTools(commands.Cog):
    """
    Tools for managing roles across all users.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

    @commands.group()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def roletools(self, ctx: commands.GuildContext):
        """Role tools commands."""
        pass

    @roletools.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def list(self, ctx: commands.GuildContext, has_roles: commands.Greedy[discord.Role]):
        """List all users with a role(s)."""
        if len(has_roles) == 0:
            await ctx.send("You must specify at least one role.")
            return
        
        members = has_roles[0].members

        if len(has_roles) > 1:
            members = [member for member in members if all(role in member.roles for role in has_roles[1:])]

        if len(members) == 0:
            await ctx.send("No users found with the specified roles.")
            return

        members_string = ", ".join(member.mention for member in members)
        await ctx.send(f"{len(members)} users with roles: {members_string}", allowed_mentions=discord.AllowedMentions.none())

    @roletools.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def add(self, ctx: commands.GuildContext, new_role: discord.Role, filter_roles: commands.Greedy[discord.Role]):
        """Adds the given role to all users who meet the filtered roles criteria."""
        if len(filter_roles) == 0:
            await ctx.send("You must specify at least one filter role.")
            return
        
        members = filter_roles[0].members

        if len(filter_roles) > 1:
            members = [member for member in members if all(role in member.roles for role in filter_roles[1:])]
        
        view = ConfirmationView(
            author=ctx.author,
        )

        filter_roles_string = ', '.join(role.mention for role in filter_roles)

        msg_string = f"Add {new_role.mention} to {len(members)} members?\n"
        msg_string += f"Only users with the following roles will be adjusted: {filter_roles_string}\n"

        confirmation_message = await ctx.send(content=msg_string, view=view)

        if await view.wait() or not view.value:
            await confirmation_message.delete()
            return
        
        await confirmation_message.edit(content=f"Adding {new_role.mention} to users...\n{f'(Only users with {filter_roles_string})' if len(filter_roles) > 0 else ''}", view=None)

        count = 0

        for member in members:
            try:
                if new_role not in member.roles:
                    await member.add_roles(new_role, reason="Role addition.")
                count += 1
            except discord.Forbidden:
                await self.bot.send_to_owners(f"RoleTools: I do not have permission to add roles for {member.mention} in {ctx.guild.name}.")

            await asyncio.sleep(1)

        await confirmation_message.edit(content=f"Added {new_role.mention} to {count} users.")

    @roletools.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def remove(self, ctx: commands.GuildContext, remove_role: discord.Role, filter_roles: commands.Greedy[discord.Role]):
        """Removes the given role from all users who meet the filtered roles criteria."""
        
        members = remove_role.members

        if len(filter_roles) > 0:
            members = [member for member in members if all(role in member.roles for role in filter_roles)]

        filter_roles_string = ', '.join(role.mention for role in filter_roles)

        if len(members) == 0:
            msg = f"No members found with the role {remove_role.mention}"
            if len(filter_roles) > 0:
                filter_roles_string = ', '.join(role.mention for role in filter_roles)
                msg += f" and the roles: {filter_roles_string}"

            msg += '.'

            await ctx.send(msg)
            return
        
        view = ConfirmationView(
            author=ctx.author,
        )

        msg_string = f"Remove {remove_role.mention} from {len(members)} members?\n"
        msg_string += f"Only users with the following roles will be adjusted: {filter_roles_string}\n"

        confirmation_message = await ctx.send(content=msg_string, view=view)

        if await view.wait() or not view.value:
            await confirmation_message.delete()
            return
        
        await confirmation_message.edit(content=f"Removing {remove_role.mention} from users...\n{f'(Only users with {filter_roles_string})' if len(filter_roles) > 0 else ''}", view=None)

        count = 0

        for member in members:
            try:
                if remove_role in member.roles:
                    await member.remove_roles(remove_role, reason="Role removal.")
                count += 1
            except discord.Forbidden:
                await self.bot.send_to_owners(f"RoleTools: I do not have permission to remove roles for {member.mention} in {ctx.guild.name}.")

            await asyncio.sleep(1)

        await confirmation_message.edit(content=f"Removed {remove_role.mention} from {count} users.")


    @roletools.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def convert(self, ctx: commands.GuildContext, from_role: discord.Role, to_role: discord.Role, filter_roles: commands.Greedy[discord.Role]):
        """Convert all users with a role to another role."""
        view = ConfirmationView(
            author=ctx.author,
        )

        members = from_role.members

        if len(filter_roles) > 0:
            members = [member for member in members if all(role in member.roles for role in filter_roles)]

        msg_string = "**__WARNING__: THIS COMMAND IS DANGEROUS**\n"
        msg_string += f"Remove {from_role.mention} from {len(members)} members and grant them {to_role.mention}?\n"

        filter_roles_string = ', '.join(role.mention for role in filter_roles)

        if len(filter_roles) > 0:
            msg_string += f"Only users with the following roles will be adjusted: {filter_roles_string}\n"

        confirmation_message = await ctx.send(content=msg_string, view=view)

        if await view.wait() or not view.value:
            await confirmation_message.delete()
            return 
        
        await confirmation_message.edit(content=f"Converting users from {from_role.mention} to {to_role.mention}...\n{f'(Only users with {filter_roles_string})' if len(filter_roles) > 0 else ''}", view=None)

        count = 0

        for member in members:
            try:
                await member.remove_roles(from_role, reason="Role conversion.")
                if to_role not in member.roles:
                    await member.add_roles(to_role, reason="Role conversion.")
                count += 1
            except discord.Forbidden:
                await self.bot.send_to_owners(f"RoleTools: I do not have permission to convert roles for {member.mention} in {ctx.guild.name}.")

            await asyncio.sleep(1)

        await confirmation_message.edit(content=f"Converted {count} users from {from_role.mention} to {to_role.mention}.")
        pass
