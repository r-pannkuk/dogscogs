from datetime import datetime, timedelta
import random
from re import match
import re
import string
from types import SimpleNamespace
from typing import Literal, Optional, Tuple, Union
import typing
import urllib

import discord
import d20
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError, URLError
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs_utils.cogs import ReactCog, DogCog, ReactGuildConfig as GuildConfig, COG_IDENTIFIER
from dogscogs_utils.adapters.parsers import Token
from dogscogs_utils.adapters.converters import ReactType


RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: GuildConfig = {
    **ReactCog.DefaultConfig,
    "name": "Welcome",
    "cooldown": {
        **ReactCog.DefaultConfig,
        "mins": 0,
    },
    "embed": {
        **ReactCog.DefaultConfig["embed"],
        "color": discord.Color.dark_green().to_rgb(),
        "use_embed": True,
        "image_url": "",
        "title": f"Welcome to the {Token.ServerName} discord, {Token.MemberName}!",
        "footer": f"You are member #{Token.MemberCount}!",
    },
    "trigger": {
        **ReactCog.DefaultConfig["trigger"],
        "type": ReactType.JOIN,
        "chance": 1,
    },
    "responses": [
        f"Please read the **#information** channel for everything you need to know about this server!",
    ],
}


class Welcomer(ReactCog):
    """
    Welcomes new users with a greeting.
    """

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(
            None,
            identifier=COG_IDENTIFIER,
            force_registration=True,
            cog_name="Welcomer"
        )
        self.config.register_guild(**DEFAULT_GUILD)

    ###########################################################################################################
    #                                                 Welcome                                                 #
    ###########################################################################################################

    @commands.hybrid_group(aliases=["welcomer"])
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome(self, ctx: commands.Context):
        """Commands for configuring the server welcome messages."""
        pass

    @welcome.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.Context):
        await DogCog.clear_all(self, ctx, True)
        pass

    @welcome.command(name="toggle", help=ReactCog.enable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_toggle(self, ctx: commands.Context):
        await super().toggle(ctx)
        pass

    @welcome.command(name="enable", help=DogCog.enable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_enable(self, ctx: commands.Context):
        await DogCog.enable(self, ctx)
        pass

    @welcome.command(name="disable", help=DogCog.disable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_disable(self, ctx: commands.Context):
        await DogCog.disable(self, ctx)
        pass

    @welcome.command(name="enabled", help=DogCog.enabled.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await DogCog.enabled(self, ctx, bool)
        pass

    @welcome.group(name="response")
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_response(self, ctx: commands.Context):
        """Configure responses for the given trigger."""
        pass

    @welcome_response.command(name="list", help=ReactCog.response_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_response_list(self, ctx: commands.Context):
        await super().response_list(ctx)
        pass

    @welcome_response.command(
        name="add",
        help=f"Adds a new welcome message for use in the server.  Use the following escaped strings for values:\n"
        + f"-- ``{Token.MemberName.value}`` - The target member's name\n"
        + f"-- ``{Token.ServerName.value}`` - The server name\n"
        f"-- ``{Token.MemberCount.value}`` - The server member count\n"
        "\n" + "Args:\n" + "\tentry (str): The new welcome message to be used at random.",
    )
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_response_add(self, ctx: commands.Context, *, msg: str):
        await super().response_add(ctx, msg)
        pass

    @welcome_response.command(name="remove", help=ReactCog.response_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_response_remove(self, ctx: commands.Context, index: int):
        await super().response_remove(ctx, index)
        pass

    @welcome.group(name="channel")
    @commands.has_guild_permissions(manage_roles=True)
    async def wecome_channel(self, ctx: commands.Context):
        """Manages channels for the trigger to respond into.
        """
        pass

    @wecome_channel.command(name="list", help=ReactCog.channel_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def wecome_channel_list(self, ctx: commands.Context):
        await super().channel_list(ctx)
        pass

    @wecome_channel.command(name="add", help=ReactCog.channel_add.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def wecome_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        await super().channel_add(ctx, channel)
        pass

    @wecome_channel.command(name="remove", help=ReactCog.channel_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def wecome_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        await super().channel_remove(ctx, channel)
        pass

    @welcome.group(name="embed")
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_embed(self, ctx: commands.Context):
        """Settings for embed configuration."""

    @welcome_embed.command(name="enabled", help=ReactCog.embed_enabled.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_embed_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await super().embed_enabled(ctx, bool)
        pass

    @welcome_embed.command(
        name="image", aliases=["thumbnail"], help=ReactCog.embed_image.__doc__
    )
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_embed_image(
        self, ctx: commands.Context, *, url: typing.Optional[str] = None
    ):
        await super().embed_image(ctx, url)
        pass

    @welcome_embed.command(name="title", help=ReactCog.embed_title.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_embed_title(
        self, ctx: commands.Context, *, title: typing.Optional[str] = None
    ):
        await super().embed_title(ctx, title)
        pass

    @welcome_embed.command(name="footer", help=ReactCog.embed_footer.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_embed_footer(
        self, ctx: commands.Context, *, footer: typing.Optional[str] = None
    ):
        await super().embed_footer(ctx, footer)
        pass

    @welcome.command(name="template", help=ReactCog.template.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def welcome_template(self, ctx: commands.Context):
        await super().template(ctx, channel=ctx.channel)
        pass
