from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "role_map": {},
}

class RoleAssign(commands.Cog):
    """
    Allows users in lower hierarchy to assign roles.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    @commands.group()
    async def roleassign(self, ctx: commands.Context):
        """
        Role assignment commands.
        """
        pass

    @roleassign.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def enable(self, ctx: commands.Context):
        """
        Enable role assignment.
        """
        await self.config.guild(ctx.guild).is_enabled.set(True)
        await ctx.send("Role assignment enabled.")
        pass

    @roleassign.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def disable(self, ctx: commands.Context):
        """
        Disable role assignment.
        """
        await self.config.guild(ctx.guild).is_enabled.set(False)
        await ctx.send("Role assignment disabled.")
        pass

    @roleassign.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """
        Check if role assignment is enabled.
        """
        if bool is None:
            bool = await self.config.guild(ctx.guild).is_enabled()

        await self.config.guild(ctx.guild).is_enabled.set(bool)
        
        await ctx.send(f"Role assignment is {'enabled' if bool else 'disabled'}.")
        pass

    @roleassign.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def add(self, ctx: commands.Context, destination_role: discord.Role, permitted_source: typing.Union[discord.Member, discord.Role]):
        """
        Configures a destination role to be assignable by a member or role.
        """
        role_map = await self.config.guild(ctx.guild).role_map()
        target_config = role_map.get(str(destination_role.id), {
            "members": [],
            "roles": [],
        })

        if isinstance(permitted_source, discord.Member):
            if permitted_source.id in target_config["members"]:
                await ctx.send("Member already has permission.")
                return
            
            target_config["members"].append(permitted_source.id)
        elif isinstance(permitted_source, discord.Role):
            if permitted_source.id in target_config["roles"]:
                await ctx.send("Role already has permission.")
                return
            
            target_config["roles"].append(permitted_source.id)
        else:
            raise ValueError("Invalid source type.")
        
        role_map[destination_role.id] = target_config

        await self.config.guild(ctx.guild).role_map.set(role_map)

        await ctx.send(f"Permission added: {permitted_source} -> {destination_role}")
        pass

    @roleassign.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def remove(self, ctx: commands.Context, destination_role: discord.Role, permitted_source: typing.Union[discord.Member, discord.Role]):
        """
        Removes permission to grant the given role.
        """
        role_map = await self.config.guild(ctx.guild).role_map()
        target_config = role_map.get(str(destination_role.id), {
            "members": [],
            "roles": [],
        })

        if isinstance(permitted_source, discord.Member):
            if permitted_source.id not in target_config["members"]:
                await ctx.send("Member does not have permission.")
                return
            
            target_config["members"].remove(permitted_source.id)
        elif isinstance(permitted_source, discord.Role):
            if permitted_source.id not in target_config["roles"]:
                await ctx.send("Role does not have permission.")
                return
            
            target_config["roles"].remove(permitted_source.id)
        else:
            raise ValueError("Invalid source type.")
        
        role_map[destination_role.id] = target_config

        await self.config.guild(ctx.guild).role_map.set(role_map)

        await ctx.send(f"Permission removed: {permitted_source} -> {destination_role}")
        pass

    @roleassign.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_channels=True)
    async def list(self, ctx: commands.Context):
        """
        List all roles with permissions.
        """
        role_map = await self.config.guild(ctx.guild).role_map()

        embed = discord.Embed(title="Role permissions")

        description = ""

        new_role_map = {}

        for role_id, role_config in role_map.items():
            destination_role = ctx.guild.get_role(int(role_id))
            if destination_role is None:
                continue

            description += f"{destination_role.mention}:\n"

            permitted_members = [member for member in [ctx.guild.get_member(int(member_id)) for member_id in role_config["members"]] if member is not None]
            permitted_roles = [role for role in [ctx.guild.get_role(int(role_id)) for role_id in role_config["roles"]] if role is not None]

            if len(permitted_members) > 0:
                description += f"-- Members: {', '.join([member.mention for member in permitted_members])}\n"
            if len(permitted_roles) > 0:
                description += f"-- Roles: {', '.join([role.mention for role in permitted_roles])}\n"

            if len(permitted_members) == 0 and len(permitted_roles) == 0:
                description += "-- No permissions configured.\n"
            else:
                new_role_map[role_id] = {
                    "members": [member.id for member in permitted_members],
                    "roles": [role.id for role in permitted_roles],
                }
        
        embed.description = description
        
        await ctx.send(embed=embed)

        await self.config.guild(ctx.guild).role_map.set(new_role_map)
        pass

    @roleassign.command()
    async def assign(self, ctx: commands.Context, role: discord.Role, member: discord.Member):
        """
        Grants the target role to the appropriate member.
        """
        role_map = await self.config.guild(ctx.guild).role_map()
        role_config = role_map.get(str(role.id), {
            "members": [],
            "roles": [],
        })

        if ctx.author.id in role_config["members"] or any([role_id in role_config["roles"] for role_id in [role.id for role in ctx.author.roles]]):
            await member.add_roles(role)
            await ctx.send(f"Role {role} assigned to {member}.")
        else:
            await ctx.send("You do not have permission to assign this role.")
        pass

    @roleassign.command()
    async def unassign(self, ctx: commands.Context, role: discord.Role, member: discord.Member):
        """
        Removes the target role from the appropriate member.
        """
        role_map = await self.config.guild(ctx.guild).role_map()
        role_config = role_map.get(str(role.id), {
            "members": [],
            "roles": [],
        })

        if ctx.author.id in role_config["members"] or any([role_id in role_config["roles"] for role_id in [role.id for role in ctx.author.roles]]):
            await member.remove_roles(role)
            await ctx.send(f"Role {role} removed from {member}.")
        else:
            await ctx.send("You do not have permission to remove this role.")
        pass