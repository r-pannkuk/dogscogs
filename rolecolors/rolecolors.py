import asyncio
from datetime import datetime
from functools import partial
import re
from typing import Literal
import typing

# import numpy as np

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from coins import Coins

from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore[import-untyped]
from apscheduler.jobstores.base import JobLookupError # type: ignore[import-untyped]

from dogscogs.constants import COG_IDENTIFIER, TIMEZONE
from dogscogs.constants.colors import color_diff, hex_to_rgb, get_palette
from dogscogs.constants.discord.embed import MAX_DESCRIPTION_LENGTH as DISCORD_EMBED_MAX_DESCRIPTION_LENGTH

scheduler = AsyncIOScheduler(timezone="US/Eastern")

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "number_of_colors": 24,
    "role_ids": [],
    "color_change_cost": 10,
    "color_change_duration_secs": 60 * 60 * 24,  # 1 day
}

DEFAULT_MEMBER = {
    "original_color_role_id": None,
    "cursed_until": None,
}

class RoleColors(commands.Cog):
    """
    Assigns color roles for a specific user.
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

        scheduler.start()

    async def _set(
        self,
        ctx: commands.GuildContext,
        member: discord.Member,
        hex_or_roleid: typing.Union[discord.Role, str],
    ) -> typing.Union[discord.Role, None]:
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]

        if len(color_roles) == 0:
            await ctx.channel.send("No color roles found.", delete_after=15)
            return None

        if isinstance(hex_or_roleid, discord.Role):
            if hex_or_roleid not in color_roles:
                await ctx.channel.send("Role was not a specified color role.", delete_after=15)
                return None
            role = hex_or_roleid
        else:
            if not isinstance(hex_or_roleid, str) or not re.match(
                r"(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$", hex_or_roleid
            ):
                await ctx.channel.send(
                    "Invalid parameter sent.  Please use `#rrggbb` format.",
                    delete_after=15
                )
                return None

            role = min(
                color_roles,
                key=lambda r: color_diff(
                    hex_to_rgb(hex_or_roleid), hex_to_rgb(f"{r.colour.value:06x}")
                ),
            )

        if role is None:
            await ctx.channel.send(
                "No color role found.  Please ask your moderator to add more color roles.",
                delete_after=15
            )
            return None

        if member.id in [member.id for member in role.members]:
            await ctx.channel.send(
                f"User {member} already has the closest color role available.",
                delete_after=15
            )
            return None

        await member.remove_roles(
            *[role for role in color_roles if role in member.roles]
        )

        await member.add_roles(role)

        return role

    @commands.group()
    async def rolecolors(self, ctx):
        """
        Manages color assignment for users based on designated color roles.
        """
        pass

    @rolecolors.command(usage="<amount>", name="create")
    @commands.has_guild_permissions(manage_roles=True)
    async def create_color_roles(
        self, ctx: commands.GuildContext, amount: typing.Optional[int]
    ) -> None:
        """
        Creates a new group of `N` color roles.  Replaces old roles in use.
        """
        default_amount = await self.config.guild_from_id(
            ctx.guild.id
        ).number_of_colors()
        if amount is None:
            amount = default_amount
        elif amount < 3:
            raise commands.BadArgument("Please enter a number higher than 2.")
        elif amount != default_amount:
            await self.config.guild_from_id(ctx.guild.id).number_of_colors.set(amount)

        message: discord.Message = await ctx.channel.send(f"Creating {amount} roles...")

        previous_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        previous_role_configs = []
        new_roles = []
        guild: discord.Guild = ctx.guild

        for role_id in previous_role_ids:
            role = guild.get_role(role_id)
            if role is None:
                continue

            previous_role_configs.append(
                {
                    "role_id": role_id,
                    "color": hex_to_rgb(f"{role.colour.value:06x}"),
                    "members": [member.id for member in role.members],
                }
            )
            await role.delete()

        await self.config.guild_from_id(ctx.guild.id).role_ids.set([])

        colors = [
            (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            for rgb in get_palette(n=amount, Lmin=5, Lmax=95, maxLoops=100000)
        ]
        # colors = [(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)) for rgb in rgb_list]
        # colors = [(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        #           for rgb in rgbs(amount)]

        for rgb in colors:
            name = "Color:#{0:02x}{1:02x}{2:02x}".format(rgb[0], rgb[1], rgb[2])
            new_roles.append(
                await guild.create_role(
                    reason="New color role through rolecolors command.",
                    name=name,
                    mentionable=False,
                    color=discord.Colour.from_rgb(rgb[0], rgb[1], rgb[2]),
                )
            )

        for role_config in previous_role_configs:

            def color_diff_current(r: discord.Role):
                return color_diff(
                    role_config["color"], hex_to_rgb(f"{r.colour.value:06x}")
                )

            closest_role: discord.Role = min(new_roles, key=color_diff_current)
            for member_id in role_config["members"]:
                member = guild.get_member(member_id)
                if member is not None:
                    await member.add_roles(closest_role)

        await self.config.guild_from_id(ctx.guild.id).role_ids.set(
            [role.id for role in new_roles]
        )

        await message.edit(content=
            f"Created {amount} color role{'s' if amount != 1 else ''} for assignment.  Members have been reassigned colors closest to their original role."
        )
        return

    @rolecolors.command(usage="<hex_or_roleid>", name="add")
    @commands.has_guild_permissions(manage_roles=True)
    async def add_color_role(
        self, ctx: commands.GuildContext, color: typing.Union[discord.Role, str]
    ) -> None:
        """
        Adds an already existing color role or creates a new one based on hex value.
        """
        guild: discord.Guild = ctx.guild
        previous_role_ids = await self.config.guild_from_id(guild.id).role_ids()

        # for color in hex_or_roleid:
        if isinstance(color, str):
            if not re.match(r"(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$", color):
                await ctx.channel.send(
                    f"Invalid parameter sent: {color}\nPlease use `#rrggbb` format."
                )
                return

            rgb = hex_to_rgb(color)

            for role in guild.roles:
                if role.id not in previous_role_ids:
                    continue

                if rgb == hex_to_rgb(f"{role.color.value:06x}"):
                    await ctx.channel.send(
                        f"{color} was already found in role (@{role.name})"
                    )
                    return

            role = await guild.create_role(
                reason="New color role through rolecolors command.",
                name=f"Color:{color}",
                mentionable=False,
                color=discord.Colour.from_rgb(rgb[0], rgb[1], rgb[2]),
            )

        elif isinstance(color, discord.Role):
            if color.id in previous_role_ids:
                await ctx.channel.send(
                    f"{color.name} is already a designated color role."
                )
                return

            role = color
            pass

        previous_role_ids.append(role.id)
        await self.config.guild_from_id(guild.id).role_ids.set(previous_role_ids)
        await ctx.channel.send(f"Added color role {role.name}.")

    @rolecolors.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def duration(self, ctx: commands.GuildContext, seconds: typing.Optional[int]):
        """
        Sets how long cursing someone's color should last.
        """
        if seconds is None:
            seconds = await self.config.guild_from_id(ctx.guild.id).color_change_duration_secs()
        
        await self.config.guild_from_id(ctx.guild.id).color_change_duration_secs.set(seconds)
        await ctx.channel.send(f"Color change curse duration set to {seconds} seconds.")

    @rolecolors.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def cost(self, ctx: commands.GuildContext, points: typing.Optional[int]):
        """
        Sets the cost for color changes.
        """
        if points is None:
            points = await self.config.guild_from_id(ctx.guild.id).color_change_cost()
        
        await self.config.guild_from_id(ctx.guild.id).color_change_cost.set(points)
        await ctx.channel.send(f"Color change curse cost set to {points} points.")

    async def _uncurse_member(self, member: discord.Member):
        color_role_ids : typing.List[int] = await self.config.guild(member.guild).role_ids()
        color_roles = [role for role in member.guild.roles if role.id in color_role_ids]
        original_color_role_id = await self.config.member(member).original_color_role_id()
        
        try:
            await member.remove_roles(*[role for role in color_roles if role in member.roles])
            if original_color_role_id is not None:
                original_color_role = member.guild.get_role(original_color_role_id)
                if original_color_role is not None:
                    await member.add_roles(original_color_role)
        except PermissionError:
            pass

        await self.config.member(member).cursed_until.set(None)

    async def _update_member(self, member: discord.Member) -> bool:
        """Checks to see if a member should be uncursed, and readds the curse to the scheduler if it's still persistant."""
        cursed_until = await self.config.member(member).cursed_until()

        if cursed_until is not None:
            if datetime.now(tz=TIMEZONE).timestamp() >= cursed_until:
                await self._uncurse_member(member)
                return True
            else:
                if not scheduler.running:
                    scheduler.start()

                scheduler.add_job(
                    partial(self._update_member, member),
                    id=f"ColorCurse:{member.id}",
                    trigger="date",
                    next_run_time=datetime.fromtimestamp(
                        cursed_until, tz=TIMEZONE
                    ),
                    replace_existing=True,
                )

        return False

    async def _check_guild(self, guild: discord.Guild) -> typing.List[discord.Member]:
        fixed_members = []

        for member in guild.members:
            cursed_until = await self.config.member(member).cursed_until()
            if cursed_until is not None:
                if await self._update_member(member):
                    fixed_members.append(member)

        return fixed_members

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            members = await self._check_guild(guild)
            if len(members) > 0:
                await self.bot.send_to_owners(
                    f"Rolecolors Cog: {len(members)} members had their curses removed in {guild.name} after restart:\n" +
                    "\n".join([f"{member.mention} ({member.id})" for member in members])
                )

    @rolecolors.command(usage="<member> <hex_or_roleid>", name="curse")
    async def curse(
        self,
        ctx: commands.GuildContext,
        member: discord.Member,
        hex_or_roleid: typing.Union[discord.Role, str],
    ):
        """Curses a target member to use a specific color role.

        Args:
            member (discord.Member): Who to curse.
            hex_or_roleid (typing.Union[discord.Role, str]): The color to curse them with.
        """
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]
        duration = await self.config.guild_from_id(
            ctx.guild.id
        ).color_change_duration_secs()
        color_change_cost = await self.config.guild_from_id(
            ctx.guild.id
        ).color_change_cost()

        if member.id == ctx.author.id:
            await ctx.channel.send("You cannot curse yourself. Try `set` instead.")
            return

        if self.bot.get_cog("Coins") is None:
            await ctx.channel.send("Coins cog is not loaded.")
            return

        current_balance = await Coins._get_balance(ctx.author)

        if current_balance < color_change_cost:
            await ctx.channel.send(
                f"You do not have enough {await Coins._get_currency_name(ctx.guild)} to change colors.  You need {color_change_cost} {await Coins._get_currency_name(ctx.guild)} and have {current_balance}."
            )
            return
        
        message = await ctx.send(f"Spend {color_change_cost} {await Coins._get_currency_name(ctx.guild)} to curse {member.mention} to use {hex_or_roleid} for {duration} seconds?")

        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30, check=check)
        except asyncio.TimeoutError:
            await message.delete()
            return
        
        if str(reaction.emoji) == "❌":
            await message.delete()
            await ctx.message.delete()
            return
        elif str(reaction.emoji) == "✅":
            await message.edit(content="🪙 Payment Accepted 🪙\nProcessing...")

        await message.clear_reactions()

        original_color_role_id = await self.config.member(member).original_color_role_id()
        if original_color_role_id is None:
            found_roles = [role for role in member.roles if role.id in color_role_ids]
            if len(found_roles) > 0:
                original_color_role_id = found_roles[0].id
                await self.config.member(member).original_color_role_id.set(original_color_role_id)

        
        set_role = await self._set(ctx, member, hex_or_roleid)

        if set_role is not None:

            # if not ctx.author.guild_permissions.manage_roles:
            await Coins._remove_balance(ctx.author, color_change_cost)

            release_timestamp = (
                datetime.now(tz=TIMEZONE).timestamp() + duration
            )

            await self.config.member(member).cursed_until.set(release_timestamp)

            if not scheduler.running:
                scheduler.start()

            async def curse_end():
                await self._uncurse_member(member)
                await ctx.channel.send(f"{member.mention} has been uncursed.")

            scheduler.add_job(
                curse_end,
                id=f"ColorCurse:{member.id}",
                trigger="date",
                next_run_time=datetime.fromtimestamp(
                    release_timestamp, tz=TIMEZONE
                ),
                replace_existing=True,
            )

            await message.edit(content=
                f"{ctx.author.mention} cursed {member.mention} to use {set_role.name} (#{set_role.color.value:06x}) until <t:{int(release_timestamp)}:F>."
            )
        else:
            await message.edit(content="You won't be charged.", delete_after=15)

    @rolecolors.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def uncurse(self, ctx: commands.GuildContext, member: discord.Member):
        """
        Removes a curse from a member.
        """ 
        if await self.config.member(member).cursed_until() is None:
            await ctx.send(f"{member.display_name} isn't cursed.", delete_after=15)
            return

        if not await self.bot.is_owner(ctx.author) and (
            # ctx.author.id != await member_config.get_cursing_instigator_id() and
            not ctx.author.guild_permissions.manage_roles
        ):
            await ctx.send(
                f"You do not have permission to remove {member.display_name}'s curse."
            )
            return

        await self._uncurse_member(member)

        await ctx.channel.send(f"{member.mention} has been uncursed.")

    @rolecolors.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def list(self, ctx: commands.GuildContext):
        """Lists all users who are affected by a curse."""
        member_configs = await self.config.all_members(ctx.guild)
        afflicted_member_ids = [key for key, value in member_configs.items() if value['cursed_until'] is not None]
        role_color_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        role_colors = [role for role in ctx.guild.roles if role.id in role_color_ids]
        
        afflicted_member_ids.sort(key=lambda x: member_configs[x]['cursed_until'])
        
        afflicted_members = [x for x in [ctx.guild.get_member(id) for id in afflicted_member_ids] if x is not None]

        if len(afflicted_members) == 0:
            await ctx.send("No members are currently cursed.")
            return

        title = f"Cursed Members"

        while len(afflicted_members) > 0:
            description = ""
            while len(afflicted_members) > 0:
                member = afflicted_members[0]
                found_roles = [role for role in member.roles if role in role_colors]

                if found_roles is None:
                    continue

                role = found_roles[0]

                time_field = f"<t:{int(datetime.fromtimestamp(member_configs[member.id]['cursed_until'], tz=TIMEZONE).timestamp())}:F>"

                string = f"{member.mention} ({member.name}) was cursed to {role.mention} until: {time_field}\n"

                if (len(description) + len(string) > DISCORD_EMBED_MAX_DESCRIPTION_LENGTH):
                    break

                description += string

                afflicted_members.pop(0)

            if len(description) == 0:
                await ctx.send(f"Something went wrong.")
                await self.bot.send_to_owners(
                    f"""`rolecolors: Failed to generate rolecolors curse list.
                    -- guild: {ctx.guild.name} <{ctx.guild.id}>
                    -- list: {afflicted_members}`"""
                )

            embed = discord.Embed(title=title, description=description)

            title = ""

            await ctx.send(embed=embed)
            pass


    @rolecolors.command(usage="<hex_or_roleid>")
    async def set(
        self, ctx: commands.GuildContext, hex_or_roleid: typing.Union[discord.Role, str]
    ):
        """
        Sets the color for a user by assigning them to the closest role.
        """
        cursed_until = await self.config.member(ctx.author).cursed_until()

        if cursed_until is not None:
            await ctx.channel.send(
                f"You are currently cursed to use a specific color until <t:{int(cursed_until)}:F>."
            )
            return

        set_role = await self._set(ctx, ctx.author, hex_or_roleid)
        if set_role is not None:
            await ctx.channel.send(
                f"User {ctx.author} assigned {set_role.name} (#{set_role.color.value:06x})."
            )

    @rolecolors.command()
    async def clear(self, ctx: commands.GuildContext):
        """
        Clears any color roles that the caller may have.
        """
        cursed_until = await self.config.member(ctx.author).cursed_until()

        if cursed_until is not None:
            await ctx.channel.send(
                f"You are currently cursed to use a specific color until <t:{int(cursed_until)}:F>."
            )
            return

        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]

        await ctx.author.remove_roles(
            *[role for role in color_roles if role in ctx.author.roles]
        )

        await ctx.channel.send(
            f"Removed any color roles from {ctx.author.display_name}"
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """
        Updates color role list with any deleted roles that the guild deletes.
        """
        color_role_ids: typing.List[int] = await self.config.guild_from_id(
            role.guild.id
        ).role_ids()

        if role.id in color_role_ids:
            color_role_ids.remove(role.id)

            await self.config.guild_from_id(role.guild.id).role_ids.set(color_role_ids)
        pass

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        await super().red_delete_data_for_user(requester=requester, user_id=user_id)
