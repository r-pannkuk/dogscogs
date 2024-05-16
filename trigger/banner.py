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
from redbot.core import commands, app_commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs_utils.cogs import (
    ReactCog,
    DogCog,
    ReactGuildConfig as GuildConfig,
    COG_IDENTIFIER,
)
from dogscogs_utils.adapters.parsers import Token
from dogscogs_utils.adapters.converters import ReactType


RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: GuildConfig = {
    **ReactCog.DefaultConfig,
    "name": "Banner",
    "embed": {
        "use_embed": True,
        "image_url": None,
        "title": f"{Token.MemberName} {Token.Action}.",
        "footer": None,
        "color": discord.Color.dark_green().to_rgb(),
    },
    "cooldown": {
        "mins": 0,
        "last_timestamp": None,
        "next": None,
    },
    "trigger": {
        **ReactCog.DefaultConfig["trigger"],
        "chance": 1.0,
        "type": ReactType.BAN | ReactType.KICK,
    },
    "responses": [f"**{Token.MemberName}** {Token.Action}.  They deserved it."],
}


class Banner(ReactCog):
    """
    User banned / kicked messages.
    """

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(
            None, identifier=COG_IDENTIFIER, force_registration=True, cog_name="Banner"
        )
        self.config.register_guild(**DEFAULT_GUILD)

    ############################################################################################################
    #                                                  Banner                                                  #
    ############################################################################################################

    @commands.hybrid_group(aliases=["kicker"])
    @commands.mod_or_permissions(manage_channels=True)
    async def banner(self, ctx: commands.Context):
        """Commands for configuring the server banned / kicked messages."""
        pass

    @banner.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.Context):
        await super().clear_all(ctx, True)
        pass

    @banner.command(name="toggle", help=ReactCog.enable.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_toggle(self, ctx: commands.Context):
        await super().toggle(ctx)
        pass

    @banner.command(name="enable", help=DogCog.enable.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_enable(self, ctx: commands.Context):
        await DogCog.enable(self, ctx)
        pass

    @banner.command(name="disable", help=DogCog.disable.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_disable(self, ctx: commands.Context):
        await DogCog.disable(self, ctx)
        pass

    @banner.command(name="enabled", help=DogCog.enabled.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await DogCog.enabled(self, ctx, bool)
        pass

    @banner.group(name="response")
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_response(self, ctx: commands.Context):
        """Configure responses for the given trigger."""
        pass

    @banner_response.command(name="list", help=ReactCog.response_list.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_response_list(self, ctx: commands.Context):
        await super().response_list(ctx)
        pass

    @banner_response.command(
        name="add",
    )
    @app_commands.describe(
        msg=f"Use these escaped strings: {','.join([t.value for t in Token._member_map_.values()])}"
    )
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_response_add(self, ctx: commands.Context, *, msg: str):
        """Adds a response for when the trigger fires.

        Args:
            msg (str): The message to respond with.
        """
        await super().response_add(ctx, msg)
        pass

    @banner_response.command(name="remove", help=ReactCog.response_remove.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_response_remove(self, ctx: commands.Context, index: int):
        await super().response_remove(ctx, index)
        pass

    @banner.group(name="channel")
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_channel(self, ctx: commands.Context):
        """Manages channels for the trigger to respond into."""
        pass

    @banner_channel.command(name="list", help=ReactCog.channel_list.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_channel_list(self, ctx: commands.Context):
        await super().channel_list(ctx)
        pass

    @banner_channel.command(name="add", help=ReactCog.channel_add.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_channel_add(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        await super().channel_add(ctx, channel)
        pass

    @banner_channel.command(name="remove", help=ReactCog.channel_remove.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_channel_remove(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        await super().channel_remove(ctx, channel)
        pass

    @banner.group(name="embed")
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_embed(self, ctx: commands.Context):
        """Settings for embed configuration."""
        pass

    @banner_embed.command(name="enabled", help=ReactCog.embed_enabled.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_embed_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await super().embed_enabled(ctx, bool)
        pass

    @banner_embed.command(
        name="image", aliases=["thumbnail"], help=ReactCog.embed_image.__doc__
    )
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_embed_image(
        self, ctx: commands.Context, *, url: typing.Optional[str] = None
    ):
        await super().embed_image(ctx, url)
        pass

    @banner_embed.command(name="title", help=ReactCog.embed_title.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_embed_title(
        self, ctx: commands.Context, *, title: typing.Optional[str] = None
    ):
        await super().embed_title(ctx, title)
        pass

    @banner_embed.command(name="footer", help=ReactCog.embed_footer.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_embed_footer(
        self, ctx: commands.Context, *, footer: typing.Optional[str] = None
    ):
        await super().embed_footer(ctx, footer)
        pass

    @banner.command(name="template", help=ReactCog.template.__doc__)
    @commands.mod_or_permissions(manage_channels=True)
    async def banner_template(self, ctx: commands.Context):
        await super().template(ctx, channel=ctx.channel)
        pass
