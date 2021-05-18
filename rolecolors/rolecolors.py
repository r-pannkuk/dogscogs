import random
import re
from typing import Literal, Iterable, Tuple
import typing
import colorsys
import itertools
import math
from fractions import Fraction
# import numpy as np

import discord
from discord.errors import InvalidArgument
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "number_of_colors": 24,
    "role_ids": []
}

HSVTuple = Tuple[Fraction, Fraction, Fraction]
RGBTuple = Tuple[float, float, float]

DEFAULT_COLORS = [
    (240, 248, 255),
    (250, 235, 215),
    (0, 255, 255),
    (127, 255, 212),
    (240, 255, 255),
    (245, 245, 220),
    (255, 228, 196),
    (0, 0, 0),
    (255, 235, 205),
    (0, 0, 255),
    (138, 43, 226),
    (165, 42, 42),
    (222, 184, 135),
    (95, 158, 160),
    (127, 255, 0),
    (210, 105, 30),
    (255, 127, 80),
    (100, 149, 237),
    (255, 248, 220),
    (220, 20, 60),
    (0, 255, 255),
    (0, 0, 139),
    (0, 139, 139),
    (184, 134, 11),
    (169, 169, 169),
    (0, 100, 0),
    (189, 183, 107),
    (139, 0, 139),
    (85, 107, 47),
    (255, 140, 0),
    (153, 50, 204),
    (139, 0, 0),
    (233, 150, 122),
    (143, 188, 143),
    (72, 61, 139),
    (47, 79, 79),
    (0, 206, 209),
    (148, 0, 211),
    (255, 20, 147),
    (0, 191, 255),
    (105, 105, 105),
    (30, 144, 255),
    (178, 34, 34),
    (255, 250, 240),
    (34, 139, 34),
    (255, 0, 255),
    (220, 220, 220),
    (248, 248, 255),
    (255, 215, 0),
    (218, 165, 32),
    (128, 128, 128),
    (0, 128, 0),
    (173, 255, 47),
    (240, 255, 240),
    (255, 105, 180),
    (205, 92, 92),
    (75, 0, 130),
    (255, 255, 240),
    (240, 230, 140),
    (230, 230, 250),
    (255, 240, 245),
    (124, 252, 0),
    (255, 250, 205),
    (173, 216, 230),
    (240, 128, 128),
    (224, 255, 255),
    (250, 250, 210),
    (144, 238, 144),
    (211, 211, 211),
    (255, 182, 193),
    (255, 160, 122),
    (32, 178, 170),
    (135, 206, 250),
    (119, 136, 153),
    (176, 196, 222),
    (255, 255, 224),
    (0, 255, 0),
    (50, 205, 50),
    (250, 240, 230),
    (255, 0, 255),
    (128, 0, 0),
    (102, 205, 170),
    (0, 0, 205),
    (186, 85, 211),
    (147, 112, 219),
    (60, 179, 113),
    (123, 104, 238),
    (0, 250, 154),
    (72, 209, 204),
    (199, 21, 133),
    (25, 25, 112),
    (245, 255, 250),
    (255, 228, 225),
    (255, 228, 181),
    (255, 222, 173),
    (0, 0, 128),
    (253, 245, 230),
    (128, 128, 0),
    (107, 142, 35),
    (255, 165, 0),
    (255, 69, 0),
    (218, 112, 214),
    (238, 232, 170),
    (152, 251, 152),
    (175, 238, 238),
    (219, 112, 147),
    (255, 239, 213),
    (255, 218, 185),
    (205, 133, 63),
    (255, 192, 203),
    (221, 160, 221),
    (176, 224, 230),
    (128, 0, 128),
    (255, 0, 0),
    (188, 143, 143),
    (65, 105, 225),
    (139, 69, 19),
    (250, 128, 114),
    (244, 164, 96),
    (46, 139, 87),
    (255, 245, 238),
    (160, 82, 45),
    (192, 192, 192),
    (135, 206, 235),
    (106, 90, 205),
    (112, 128, 144),
    (255, 250, 250),
    (0, 255, 127),
    (70, 130, 180),
    (210, 180, 140),
    (0, 128, 128),
    (216, 191, 216),
    (255, 99, 71),
    (64, 224, 208),
    (238, 130, 238),
    (245, 222, 179),
    (255, 255, 255),
    (245, 245, 245),
    (255, 255, 0),
    (154, 205, 50)
]


def color_diff(rgb1, rgb2):
    if isinstance(rgb1, discord.Colour):
        rgb1 = (rgb1.r, rgb1.g, rgb1.b)
    if isinstance(rgb2, discord.Colour):
        rgb2 = (rgb2.r, rgb2.g, rgb2.b)

    return (abs(rgb1[0]-rgb2[0])**2 + abs(rgb1[1]-rgb2[1])**2 + abs(rgb1[2]-rgb2[2])**2)


def sort_palette(color):
    hls = colorsys.rgb_to_hls(color[0] / 255, color[1] / 255, color[2] / 255)
    return hls[0] * 100 + hls[1] * 5 + hls[2] * 5


def aggregate_palette(p):
    result = 0
    for a, b in itertools.combinations(p, 2):
        result += color_diff(a, b)

    return result / len(p)


def min_palette_diff(p):
    min = None
    for a, b in itertools.combinations(p, 2):
        diff = color_diff(a, b)
        if min == None or diff < min:
            min = diff
    return diff


def get_palette(n: int = 100, Lmin: int = 5, Lmax: int = 90, maxLoops: int = 100000) -> Iterable[RGBTuple]:
    data = []

    for color in DEFAULT_COLORS:
        hls = colorsys.rgb_to_hls(
            color[0] / 255, color[1] / 255, color[2] / 255)
        L = 100 * hls[1]
        if ((L >= Lmin) and (L <= Lmax)):
            data.append(color)

    palettes = []

    for i in range(0, maxLoops):
        palettes.append(random.sample(data, k=n))

    palettes.sort(key=min_palette_diff, reverse=True)

    bestPalette = palettes[0]

    bestPalette.sort(key=sort_palette)

    return bestPalette


def rgbs(num_colors) -> Iterable[RGBTuple]:
    colors = [(0.08, 0.08, 0.08), (1, 1, 1), (0.5, 0.5, 0.5)]
    if num_colors > 3:
        for i in np.arange(0., 360., 360. / (num_colors - 3)):
            hue = i/360.
            lightness = (50 + np.random.rand() * 10)/100.
            saturation = (90 + np.random.rand() * 10)/100.
            colors.append(colorsys.hls_to_rgb(hue, lightness, saturation))
    return colors


# https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
def hex_to_rgb(h) -> Tuple[int, int, int]:
    h = h.replace('#', '').replace('0x', '').replace('0X', '')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class RoleColors(commands.Cog):
    """
    Assigns color roles for a specific user.
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
    async def rolecolors(self, ctx):
        pass

    @rolecolors.command(usage="<amount>", name="create")
    @commands.mod_or_permissions(manage_roles=True)
    async def create_color_roles(self,
                                 ctx: commands.Context,
                                 amount: typing.Optional[int]) -> None:
        default_amount = await self.config.guild_from_id(
            ctx.guild.id).number_of_colors()
        if amount is None:
            amount = default_amount
        elif amount < 3:
            raise InvalidArgument("Please enter a number higher than 2.")
        elif amount != default_amount:
            await self.config.guild_from_id(ctx.guild.id).number_of_colors.set(amount)

        message: discord.Message = await ctx.channel.send(f"Creating {amount} roles...")

        previous_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        previous_role_configs = []
        new_roles = []
        guild: discord.Guild = ctx.guild

        for role_id in previous_role_ids:
            role: discord.Role = guild.get_role(role_id)
            if role is None:
                continue

            previous_role_configs.append({
                "role_id": role_id,
                "color": hex_to_rgb(f'{role.colour.value:06x}'),
                "members": [member.id for member in role.members],
            })
            await role.delete()

        await self.config.guild_from_id(ctx.guild.id).role_ids.set([])

        colors = [(int(rgb[0]), int(rgb[1]), int(rgb[2]))
                  for rgb in get_palette(n=amount, Lmin=5, Lmax=95, maxLoops=100000)]
        # colors = [(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)) for rgb in rgb_list]
        # colors = [(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        #           for rgb in rgbs(amount)]

        for rgb in colors:
            name = "Color:#{0:02x}{1:02x}{2:02x}".format(
                rgb[0], rgb[1], rgb[2])
            new_roles.append(
                await guild.create_role(reason="New color role through rolecolors command.",
                                        name=name,
                                        mentionable=False,
                                        color=discord.Colour.from_rgb(rgb[0], rgb[1], rgb[2])))

        for role_config in previous_role_configs:
            def color_diff_current(r: discord.Role):
                return color_diff(role_config["color"], hex_to_rgb(f'{r.colour.value:06x}'))

            closest_role: discord.Role = min(new_roles, key=color_diff_current)
            for member_id in role_config["members"]:
                member: discord.Member = guild.get_member(member_id)
                await member.add_roles(closest_role)

        await self.config.guild_from_id(ctx.guild.id).role_ids.set([role.id for role in new_roles])

        await message.edit(f"Created {amount} color role{'s' if amount != 1 else ''} for assignment.  Members have been reassigned colors closest to their original role.")
        return

    @rolecolors.command(usage="<hex_or_roleid>", name="add")
    @commands.mod_or_permissions(manage_roles=True)
    async def add_color_role(self,
                             ctx: commands.Context,
                             color: typing.Union[discord.Role, str]) -> None:
        guild: discord.Guild = ctx.guild
        previous_role_ids = await self.config.guild_from_id(guild.id).role_ids()

        # for color in hex_or_roleid:
        if isinstance(color, str):
            if not re.match(r'(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$', color):
                await ctx.channel.send(f"Invalid parameter sent: {color}\nPlease use `#rrggbb` format.")
                return

            rgb = hex_to_rgb(color)

            for role in guild.roles:
                if role.id not in previous_role_ids:
                    continue

                if rgb == hex_to_rgb(f"{role.color.value:06x}"):
                    await ctx.channel.send(f"{color} was already found in role (@{role.name})")
                    return

            role = await guild.create_role(reason="New color role through rolecolors command.",
                                            name=f"Color:{color}",
                                            mentionable=False,
                                            color=discord.Colour.from_rgb(rgb[0], rgb[1], rgb[2]))

        elif isinstance(color, discord.Role):
            if color.id in previous_role_ids:
                await ctx.channel.send(f"{color.name} is already a designated color role.")
                return

            role = color
            pass

        previous_role_ids.append(role.id)
        await self.config.guild_from_id(guild.id).role_ids.set(previous_role_ids)
        await ctx.channel.send(f"Added color role {role.name}.")


    @rolecolors.command(usage="<hex_or_roleid>")
    async def set(self, ctx: commands.Context, hex_or_roleid: typing.Union[discord.Role, str]):
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [
            role for role in ctx.guild.roles if role.id in color_role_ids]

        if isinstance(hex_or_roleid, discord.Role):
            if hex_or_roleid not in color_roles:
                await ctx.channel.send("Role was not a specified color role.")
                return
            role = hex_or_roleid
            pass
        else:
            if not isinstance(hex_or_roleid, str) or not re.match(r'(?i)^#([0-9a-f]{6}|[0-9a-f]{3})$', hex_or_roleid):
                await ctx.channel.send("Invalid parameter sent.  Please use `#rrggbb` format.")
                return

            role: discord.Role = min(color_roles, key=lambda r: color_diff(
                hex_to_rgb(hex_or_roleid), hex_to_rgb(f'{r.colour.value:06x}')))

        if role is None:
            await ctx.channel.send("No color role found.  Please ask your moderator to add more color roles.")
            return

        if ctx.author.id in [member.id for member in role.members]:
            await ctx.channel.send("User {0} already has the closest color role available.".format(ctx.author))
            return

        await ctx.author.remove_roles(*[role for role in color_roles if role in ctx.author.roles])

        await ctx.author.add_roles(role)

        await ctx.channel.send(f"User {ctx.author} assigned {role.name} (#{role.color.value:06x}).")


    @rolecolors.command()
    async def clear(self, ctx: commands.Context):
        color_role_ids = await self.config.guild_from_id(ctx.guild.id).role_ids()
        color_roles = [
            role for role in ctx.guild.roles if role.id in color_role_ids]

        await ctx.author.remove_roles(*[role for role in color_roles if role in ctx.author.roles])

        await ctx.channel.send(f"Removed any color roles from {ctx.author.display_name}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role : discord.Role):
        color_role_ids : typing.List[int] = await self.config.guild_from_id(role.guild.id).role_ids()

        if role.id in color_role_ids:
            color_role_ids.remove(role.id)

            await self.config.guild_from_id(role.guild.id).role_ids.set(color_role_ids)
        pass


    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
