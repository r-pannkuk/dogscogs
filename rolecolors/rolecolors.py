import asyncio
from datetime import datetime, timedelta
from functools import partial
import re
from typing import Literal
import typing

# import numpy as np
import d20 # type: ignore[import-untyped]

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore[import-untyped]
from apscheduler.jobstores.base import JobLookupError # type: ignore[import-untyped]

from dogscogs.constants import COG_IDENTIFIER, TIMEZONE
from dogscogs.constants.colors import color_diff, hex_to_rgb, get_palette
from dogscogs.constants.discord.embed import MAX_DESCRIPTION_LENGTH as DISCORD_EMBED_MAX_DESCRIPTION_LENGTH
from dogscogs.parsers.date import parse_duration_string, duration_string
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.core.converter import DogCogConverter

from coins import Coins
from battler import Battler

scheduler = AsyncIOScheduler(timezone="US/Eastern")

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "number_of_colors": 24,
    "role_ids": [],
    "color_change_cost": 10,
    "color_change_duration_secs": 60 * 60 * 24,  # 1 day
    "curse_succesive_increase": 1.0,
    "curse_succesive_max": 5,
}

DEFAULT_MEMBER = {
    "original_color_role_id": None,
    "cursed_until": None,
    "successive": {
        "Painted": {
            "count": 0,
            "last_timestamp": None,
        },
    }
}

class ColorRoleConverter(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.GuildContext, argument: str) -> discord.Role: # type: ignore[override]
        config = Config.get_conf(
            cog_instance=None,
            cog_name="RoleColors",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        color_role_ids = await config.guild(ctx.guild).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]

        if len(color_roles) == 0:
            raise commands.BadArgument("No color roles found.  Please ask your moderator to add more color roles.")
        
        try:
            role = await commands.RoleConverter().convert(ctx, argument)
            if role.id not in color_role_ids:
                raise commands.BadArgument(f"Role is not a color role: {role.mention}.")
            return role
        except commands.RoleNotFound:
            pass

        if not re.match(
            r"(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$", argument
        ):
            try:
                color : discord.Color = getattr(discord.Colour, argument.lower())()
                role = min(
                    color_roles,
                    key=lambda r: color_diff(
                        (color.r, color.g, color.b), hex_to_rgb(f"{r.colour.value:06x}")
                    )
                )
            except:
                raise commands.BadArgument(f"Invalid hex color format: `{argument}`.  Please use `#rrggbb`.")
        else:
            role = min(
                color_roles,
                key=lambda r: color_diff(
                    hex_to_rgb(argument), hex_to_rgb(f"{r.colour.value:06x}")
                ),
            )

        if role is None:
            raise commands.BadArgument("No color role found.  Please ask your moderator to add more color roles.")
        elif role.id not in color_role_ids:
            raise commands.BadArgument(f"String is not a color role: {argument}.")
        
        return role

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
        role: discord.Role,
    ) -> typing.Union[discord.Role, None]:
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]

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
        self, ctx: commands.GuildContext, role: typing.Union[discord.Role, str]
    ) -> None:
        """
        Adds an already existing color role or creates a new one based on hex value.
        """
        guild: discord.Guild = ctx.guild
        previous_role_ids = await self.config.guild_from_id(guild.id).role_ids()

        if isinstance(role, discord.Role):
            if role.id in previous_role_ids:
                await ctx.channel.send("Role already exists.")
                return
            
        elif isinstance(role, str):
            if re.match(
                r"(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$", role
            ):
                color = discord.Colour.from_rgb(*hex_to_rgb(role))
            else:
                try:
                    color = getattr(discord.Colour, role.lower())()
                except:
                    await ctx.channel.send("Invalid hex color format.  Please use `#rrggbb`.")
                    return

            name = f"Color:#{color.value:06x}"

            if any([role.id in previous_role_ids for role in guild.roles if role.name == name]):
                await ctx.channel.send("Role already exists.")
                return
            
            role = await guild.create_role(
                colour=color,
                name=name,
                mentionable=False,
            )

        previous_role_ids.append(role.id)
        await self.config.guild_from_id(guild.id).role_ids.set(previous_role_ids)
        await ctx.channel.send(f"Added color role {role.mention}.")

    @rolecolors.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def duration(self, ctx: commands.GuildContext, duration_sec: typing.Optional[typing.Union[int, str]] = None):
        """
        Sets how long cursing someone's color should last.

        Args:
            duration_sec (typing.Optional[int], optional): The amount (in seconds) a user should be cursed for.
        """
        guild: discord.Guild = ctx.guild

        if duration_sec is None:
            duration_sec = int(await self.config.guild(guild).color_change_duration_secs())
            pass
        else:
            if isinstance(duration_sec, str):
                try:
                    duration_sec = parse_duration_string(duration_sec)
                except commands.BadArgument:
                    await ctx.send(
                        "Unable to parse duration input. Please use a valid format:\n-- HH:MM:SS\n-- MM:SS\n-- integer (seconds)"
                    )
                    return

            await self.config.guild(guild).color_change_duration_secs.set(duration_sec)

            pass

        seconds = duration_sec % 60
        minutes = int(duration_sec / 60) % 60
        hours = int(duration_sec / 60 / 60)

        await ctx.send(
            f"Curse duration currently set to {duration_string(hours, minutes, seconds)}."
        )
        pass

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

    async def cog_load(self):
        for guild in self.bot.guilds:
            members = await self._check_guild(guild)
            if len(members) > 0:
                await self.bot.send_to_owners(
                    f"Rolecolors Cog: {len(members)} members had their curses removed in {guild.name} after restart:\n" +
                    "\n".join([f"{member.mention} ({member.id})" for member in members])
                )

    async def _calculate_cost(self, member: discord.Member) -> int:
        """Calculates the cost of a curse for a member. Resets every end of week (Sunday).
        """
        cost  = await self.config.guild(member).color_change_cost()

        successive_cost_increase = await self.config.guild(member.guild).curse_succesive_increase()
        successive_count_max = await self.config.guild(member.guild).curse_succesive_max()

        successive = await self.config.member(member).successive()

        now = datetime.now(tz=TIMEZONE)

        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        if successive['Painted']['last_timestamp'] is not None and successive['Painted']['last_timestamp'] < start_of_week.timestamp():
            successive['Painted']['count'] = 0
            await self.config.member(member).successive.set(successive)

        cost += int(min(successive_count_max, successive['Painted']['count']) * cost * successive_cost_increase)

        return cost

    @rolecolors.command(usage="<member> <hex_or_roleid>", name="curse")
    async def curse(
        self,
        ctx: commands.GuildContext,
        target: discord.Member,
        role: typing.Annotated[discord.Role, ColorRoleConverter],
    ):
        """Curses a target member to use a specific color role.

        Args:
            target (discord.Member): Who to curse.
            role (typing.Union[discord.Role, str]): The color to curse them with. Use #rrggbb or a color role.
        """
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [role for role in ctx.guild.roles if role.id in color_role_ids]

        curse_duration_secs = await self.config.guild_from_id(
            ctx.guild.id
        ).color_change_duration_secs()

        if target.id == ctx.author.id:
            await ctx.channel.send("You cannot curse yourself. Try `set` instead.")
            return

        if self.bot.get_cog("Coins") is None:
            await ctx.channel.send("Coins cog is not loaded.")
            return
        
        if self.bot.get_cog("Battler") is None:
            await ctx.channel.send("Battler cog is not loaded.")
            return

        if len(color_roles) == 0:
            await ctx.channel.send("No color roles found.", delete_after=15)
            return None

        current_balance = await Coins._get_balance(ctx.author)
        color_change_cost = await self._calculate_cost(ctx.author)

        if current_balance < color_change_cost:
            await ctx.channel.send(
                f"You do not have enough {await Coins._get_currency_name(ctx.guild)} to change colors.  You need {color_change_cost} {await Coins._get_currency_name(ctx.guild)} and have {current_balance}."
            )
            return
        
        confirm = ConfirmationView(author=ctx.author)

        message = await ctx.send(
            content=f"Spend {color_change_cost} {await Coins._get_currency_name(ctx.guild)} to try to paint {target.mention} {role.mention}? (Balance: `{current_balance}`)",
            view=confirm
        )

        await confirm.wait()

        if not confirm.value:
            await message.delete()
            return

        await message.edit(content="🪙 Payment Accepted 🪙\nProcessing...",view=None)

        attacker_roll, defender_roll, winner = await Battler._battle(
            ctx.author, target, battle_types=['rolecolors']
        )

        cursed_users: typing.List[discord.Member] = []

        if attacker_roll.crit == d20.CritType.FAIL:
            cursed_users.append(ctx.author)
            pass
        elif attacker_roll.crit == d20.CritType.CRIT:
            curse_duration_secs *= 2
            pass

        if defender_roll.crit == d20.CritType.CRIT:
            collateral_list: typing.List[discord.Member] = await Battler._collateral(
                ctx, attacker=ctx.author, defender=target, count=1
            )

            if len(collateral_list) > 0:
                cursed_users.extend(collateral_list)
                pass

            if attacker_roll.crit == d20.CritType.CRIT and winner.id == ctx.author.id:
                cursed_users.append(target)
        elif winner.id == ctx.author.id:
            cursed_users.append(target)

        expiration = datetime.now(tz=TIMEZONE) + timedelta(seconds=curse_duration_secs)

        message_components = await Battler._battle_response(
            type="rolecolors",
            attacker=ctx.author,
            defender=target,
            attacker_roll=attacker_roll,
            defender_roll=defender_roll,
            winner=winner,
            outcome=role,
            victims=cursed_users,
            expiration=expiration,
        )

        if 'content' not in message_components:
            message_components['content'] = None
        
        new_balance = await Coins._remove_balance(ctx.author, color_change_cost)

        for cursed_user in cursed_users:
            original_color_role_id = await self.config.member(cursed_user).original_color_role_id()
            if original_color_role_id is None:
                found_roles = [role for role in cursed_user.roles if role.id in color_role_ids]
                if len(found_roles) > 0:
                    original_color_role_id = found_roles[0].id
                    await self.config.member(cursed_user).original_color_role_id.set(original_color_role_id)

            
            set_role = await self._set(ctx, cursed_user, role)

            if set_role is not None:
                await self.config.member(cursed_user).cursed_until.set(expiration.timestamp())

                if not scheduler.running:
                    scheduler.start()

                async def curse_end():
                    await self._uncurse_member(cursed_user)
                    await ctx.channel.send(f"{cursed_user.mention} has been uncursed.")

                successive = await self.config.member(ctx.author).successive()
                successive['Painted']["count"] += 1
                successive['Painted']["last_timestamp"] = datetime.now(tz=TIMEZONE).timestamp()
                await self.config.member(ctx.author).successive.set(successive)

                scheduler.add_job(
                    curse_end,
                    id=f"ColorCurse:{cursed_user.id}",
                    trigger="date",
                    next_run_time=expiration,
                    replace_existing=True,
                )

        try:
            await Battler._send_battler_dm(ctx.author, content=f"You spent `{color_change_cost} {await Coins._get_currency_name(ctx.guild)} to try to curse {target.display_name}`\nNew Balance: `{new_balance}`", silent=True)
        except discord.Forbidden as e:
            await ctx.channel.send(f"{ctx.author.mention} spent `{color_change_cost} {await Coins._get_currency_name(ctx.guild)} to try to curse {target.display_name}`\nNew Balance: `{new_balance}`", silent=True)

        await ctx.message.delete()
        await message.edit(**message_components) # type: ignore[arg-type]
        

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
    async def set(self, ctx: commands.GuildContext, role: typing.Annotated[discord.Role, ColorRoleConverter]):
        """
        Sets the color for a user by assigning them to the closest role.
        """
        cursed_until = await self.config.member(ctx.author).cursed_until()

        if cursed_until is not None:
            await ctx.channel.send(
                f"You are currently cursed to use a specific color until <t:{int(cursed_until)}:F>."
            )
            return

        set_role = await self._set(ctx, ctx.author, role)
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
