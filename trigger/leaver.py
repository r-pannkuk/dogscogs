from datetime import datetime, timedelta
import inspect
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
import docstring_parser
import pytz
from redbot.core import commands, app_commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs_utils.cogs import (
    docstring,
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
    "name": "Leaver",
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
        "type": ReactType.LEAVE,
    },
    "responses": [
        f"**{Token.MemberName}** has left us.  Press :regional_indicator_f: to pay respects.",
        f"**{Token.MemberName}** has left the server.  Good riddance.",
        f"**{Token.MemberName}** has left the building.  Don't let the door hit you on the way out.",
    ],
}


class Leaver(ReactCog):
    """
    Leaving user messages.
    """

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(
            None, identifier=COG_IDENTIFIER, force_registration=True, cog_name="Leaver"
        )
        self.config.register_guild(**DEFAULT_GUILD)

    ############################################################################################################
    #                                                  Leaver                                                  #
    ############################################################################################################

    @commands.hybrid_group(aliases=["departure", "goodbye"])
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver(self, ctx: commands.Context):
        """Commands for configuring the server leaving messages."""
        pass

    @leaver.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.Context):
        await super().clear_all(ctx, True)
        pass

    @leaver.command(name="toggle", help=ReactCog.toggle.__doc__)
    @docstring(ReactCog.toggle)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_toggle(self, ctx: commands.Context):
        await super().toggle(ctx)
        pass

    @leaver.command(name="enable", help=DogCog.enable.__doc__)
    @docstring(ReactCog.enable)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_enable(self, ctx: commands.Context):
        await DogCog.enable(self, ctx)
        pass

    @leaver.command(name="disable", help=DogCog.disable.__doc__)
    @docstring(ReactCog.disable)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_disable(self, ctx: commands.Context):
        await DogCog.disable(self, ctx)
        pass

    @leaver.command(name="enabled", help=DogCog.enabled.__doc__)
    @docstring(ReactCog.enabled)
    @commands.has_guild_permissions(manage_roles=True)
    # @app_commands.describe(
    #     bool=docstring_parser.parse(DogCog.enabled.__doc__).params[0].description
    # )
    async def leaver_enabled(
        self, ctx: commands.Context, is_enabled: typing.Optional[bool] = None
    ):
        await DogCog.enabled(self, ctx, is_enabled)
        pass

    @leaver.group(name="response")
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_response(self, ctx: commands.Context):
        """Configure responses for the given trigger."""
        pass

    @leaver_response.command(name="list", help=ReactCog.response_list.__doc__)
    @docstring(ReactCog.response_list)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_response_list(self, ctx: commands.Context):
        await super().response_list(ctx)
        pass

    @leaver_response.command(name="add", help=ReactCog.response_add.__doc__)
    @docstring(ReactCog.response_add)
    @commands.has_guild_permissions(manage_roles=True)
    @app_commands.describe(
        msg=f"Use these escaped strings: {','.join([t.value for t in Token._member_map_.values()])}"
    )
    async def leaver_response_add(self, ctx: commands.Context, *, msg: str):
        """Adds a response for when the trigger fires.

        Args:
            msg (str): The message to respond with.
        """
        await super().response_add(ctx, msg)
        pass

    @leaver_response.command(name="remove", help=ReactCog.response_remove.__doc__)
    @docstring(ReactCog.response_remove)
    @commands.has_guild_permissions(manage_roles=True)
    @docstring(ReactCog.response_remove.__doc__)
    async def leaver_response_remove(self, ctx: commands.Context, index: int):
        await super().response_remove(ctx, index)
        pass

    @leaver.group(name="channel")
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_channel(self, ctx: commands.Context):
        """Manages channels for the trigger to respond into."""
        pass

    @leaver_channel.command(name="list", help=ReactCog.channel_list.__doc__)
    @docstring(ReactCog.channel_list)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_channel_list(self, ctx: commands.Context):
        await super().channel_list(ctx)
        pass

    @leaver_channel.command(name="add", help=ReactCog.channel_add.__doc__)
    @docstring(ReactCog.channel_add)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_channel_add(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        await super().channel_add(ctx, channel)
        pass

    @leaver_channel.command(name="remove", help=ReactCog.channel_remove.__doc__)
    @docstring(ReactCog.channel_remove)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_channel_remove(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        await super().channel_remove(ctx, channel)
        pass

    @leaver.group(name="embed")
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_embed(self, ctx: commands.Context):
        """Settings for embed configuration."""
        pass

    @leaver_embed.command(name="enabled", help=ReactCog.embed_enabled.__doc__)
    @docstring(ReactCog.embed_enabled)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_embed_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await super().embed_enabled(ctx, bool)
        pass

    @leaver_embed.command(
        name="image", aliases=["thumbnail"], help=ReactCog.embed_image.__doc__
    )
    @docstring(ReactCog.embed_image)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_embed_image(
        self, ctx: commands.Context, *, url: typing.Optional[str] = None
    ):
        await super().embed_image(ctx, url)
        pass

    @leaver_embed.command(name="title", help=ReactCog.embed_title.__doc__)
    @docstring(ReactCog.embed_title)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_embed_title(
        self, ctx: commands.Context, *, title: typing.Optional[str] = None
    ):
        await super().embed_title(ctx, title)
        pass

    @leaver_embed.command(name="footer", help=ReactCog.embed_footer.__doc__)
    @docstring(ReactCog.embed_footer)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_embed_footer(
        self, ctx: commands.Context, *, footer: typing.Optional[str] = None
    ):
        await super().embed_footer(ctx, footer)
        pass

    @leaver.command(name="template", help=ReactCog.template.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def leaver_template(self, ctx: commands.Context):
        await super().template(ctx, channel=ctx.channel)
        pass
