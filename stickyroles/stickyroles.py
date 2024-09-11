from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from types import SimpleNamespace

from dogscogs.constants import COG_IDENTIFIER

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True
}

DEFAULT_MEMBER = {
    "previous_roles": []
} # type: ignore[var-annotated]

class StickyRoles(commands.Cog):
    """
    Returns user roles on rejoining.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

        self.config.register_member(**DEFAULT_MEMBER)

    
    @commands.hybrid_group()
    @commands.has_guild_permissions(manage_roles=True)
    async def stickyroles(self, ctx: commands.Context):
        """Reapplies roles to users who rejoin.
        """
        pass

    @stickyroles.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, is_enabled: typing.Optional[bool]):
        """Enables or disables the cog.

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

        await ctx.send(f"Sticky roles is currently {status_msg}.")

        pass

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Restore status.
        """
        guild: discord.Guild = member.guild

        if not (await self.config.guild(guild).is_enabled()):
            return
        
        bot_top_role = guild.get_member(self.bot.user.id).top_role # type: ignore[union-attr]

        previous_roles = await self.config.member(member).previous_roles()
        
        roles = await member.guild.fetch_roles()
        roles = [role for role in roles if role.id in previous_roles and not role.is_default() and role.position < bot_top_role.position]

        if len(roles) > 0:
            for role in roles:
                try:
                    await member.add_roles(role, reason="Reapplying user roles on rejoin.")
                except discord.Forbidden:
                    print(f"Failed to apply role '{role.name}' to {member.name} ({member.id})")
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """
        Remember roles the user had.
        """
        roles = [role.id for role in member.roles]

        await self.config.member(member).previous_roles.set(roles)
        pass