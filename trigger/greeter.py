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

from dogscogs_utils.cogs import (
    ReactCog,
    DogCog,
    ReactGuildConfig as GuildConfig,
    COG_IDENTIFIER
)
from dogscogs_utils.adapters.parsers import Token
from dogscogs_utils.adapters.converters import Percent, PhraseOrIndex, ReactType


RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: GuildConfig = {
    **ReactCog.DefaultConfig,
    "name": "Greeting",
    "embed": {
        "use_embed": False,
        "image_url": None,
        "title": None,
        "footer": None,
        "color": discord.Color.dark_green().to_rgb(),
    },
    "cooldown": {
        "mins": "1d6",
        "last_timestamp": None,
        "next": None,
    },
    "trigger": {
        **ReactCog.DefaultConfig["trigger"],
        "chance": 0.04,
        "type": ReactType.MESSAGE,
        "list": [
            f"hello",
            f"hi",
            f"salutations",
            f"konnichiwa",
            f"greetings",
            f"ohayuyu",
            f"hey there",
            f"bonjour",
            f"yo",
            f"sup",
            f"hola",
            f"ahoy",
            f"good morning",
            f"good afternoon",
            f"good evening",
            f"remibot",
        ],
    },
    "responses": [
        f"Hello, {Token.MemberName}.",
        f"Hi, {Token.MemberName}.",
        f"Salutations, {Token.MemberName}.",
        f"Konnichiwa, {Token.MemberName}.",
        f"Hello there, {Token.MemberName}.",
        f"Shut up, {Token.MemberName}.",
        f"Ohayuyu, {Token.MemberName}.",
        f"Hey there, {Token.MemberName}.",
        f"Hola, {Token.MemberName}.",
        f"Hey you, {Token.MemberName}.",
        f"How're you doing today, {Token.MemberName}?",
        f"I hope your day has been well, {Token.MemberName}.",
        f"I-it's not like I'm interested in how your day has been, {Token.MemberName}.",
        f"I-it's not like I want to greet you or anything, {Token.MemberName}.",
    ],
}

class Greeter(ReactCog):
    """
    Greets users.
    """

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(
            None,
            identifier=COG_IDENTIFIER,
            force_registration=True,
            cog_name="Greeter"
        )
        self.config.register_guild(**DEFAULT_GUILD)

    ###########################################################################################################
    #                                                  Hello                                                  #
    ###########################################################################################################

    @commands.hybrid_group(aliases=["greeter"])
    @commands.has_guild_permissions(manage_roles=True)
    async def hello(self, ctx: commands.Context):
        """Commands for configuring the server hello messages."""
        pass

    @hello.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.Context):
        await super().clear_all(ctx, True)
        pass

    @hello.command(name="toggle", help=ReactCog.enable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_toggle(self, ctx: commands.Context):
        await super().toggle(ctx)
        pass

    @hello.command(name="enable", help=DogCog.enable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_enable(self, ctx: commands.Context):
        await DogCog.enable(self, ctx)
        pass

    @hello.command(name="disable", help=DogCog.disable.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_disable(self, ctx: commands.Context):
        await DogCog.disable(self, ctx)
        pass

    @hello.command(name="enabled", help=DogCog.enabled.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await DogCog.enabled(self, ctx, bool)
        pass

    @hello.group(name="response")
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_response(self, ctx: commands.Context):
        """Configure responses for the given trigger."""
        pass

    @hello_response.command(name="list", help=ReactCog.response_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_response_list(self, ctx: commands.Context):
        await super().response_list(ctx)
        pass

    @hello_response.command(
        name="add",
        help=f"Adds a new hello message for use in the server.  Use the following escaped strings for values:\n"
        + f"-- ``{Token.MemberName.value}`` - The target member's name\n"
        + f"-- ``{Token.ServerName.value}`` - The server name\n"
        f"-- ``{Token.MemberCount.value}`` - The server member count\n"
        "\n" + "Args:\n" + "\tentry (str): The new hello message to be used at random.",
    )
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_response_add(self, ctx: commands.Context, *, msg: str):
        await super().response_add(ctx, msg)
        pass

    @hello_response.command(name="remove", help=ReactCog.response_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_response_remove(self, ctx: commands.Context, index: int):
        await super().response_remove(ctx, index)
        pass

    @hello.group(name="channel")
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_channel(self, ctx: commands.Context):
        """Manages channels for the trigger to respond into.
        """
        pass

    @hello_channel.command(name="list", help=ReactCog.channel_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_channel_list(self, ctx: commands.Context):
        await super().channel_list(ctx)
        pass

    @hello_channel.command(name="add", help=ReactCog.channel_add.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        await super().channel_add(ctx, channel)
        pass

    @hello_channel.command(name="remove", help=ReactCog.channel_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        await super().channel_remove(ctx, channel)
        pass

    @hello.group(name="embed")
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_embed(self, ctx: commands.Context):
        """Settings for embed configuration."""
        pass

    @hello_embed.command(name="enabled", help=ReactCog.embed_enabled.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_embed_enabled(
        self, ctx: commands.Context, bool: typing.Optional[bool] = None
    ):
        await super().embed_enabled(ctx, bool)
        pass

    @hello_embed.command(
        name="image", aliases=["thumbnail"], help=ReactCog.embed_image.__doc__
    )
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_embed_image(
        self, ctx: commands.Context, *, url: typing.Optional[str] = None
    ):
        await super().embed_image(ctx, url)
        pass

    @hello_embed.command(name="title", help=ReactCog.embed_title.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_embed_title(
        self, ctx: commands.Context, *, title: typing.Optional[str] = None
    ):
        await super().embed_title(ctx, title)
        pass

    @hello_embed.command(name="footer", help=ReactCog.embed_footer.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_embed_footer(
        self, ctx: commands.Context, *, footer: typing.Optional[str] = None
    ):
        await super().embed_footer(ctx, footer)
        pass

    @hello.command(name="template", help=ReactCog.template.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_template(self, ctx: commands.Context):
        await super().template(ctx, channel=ctx.channel)
        pass

    @hello.command(name="cooldown", help=ReactCog.cooldown.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_cooldown(
        self, ctx: commands.Context, *, cooldown: typing.Optional[str]
    ):
        await super().cooldown(ctx=ctx, cooldown=cooldown)
        pass

    @hello.command(name="chance", help=ReactCog.chance.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_chance(
        self, ctx: commands.Context, *, chance: typing.Optional[Percent]
    ):
        await super().chance(ctx, chance)
        pass

    @hello.group(name="always")
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_always(self, ctx: commands.Context):
        """Sets the list of users who will always receive hello messages."""
        pass

    @hello_always.command(name="list", help=ReactCog.always_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_always_list(self, ctx: commands.Context):
        await super().always_list(ctx)
        pass

    @hello_always.command(name="add", help=ReactCog.always_add.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_always_add(self, ctx: commands.Context, member: discord.Member):
        await super().always_add(ctx, member)
        pass

    @hello_always.command(name="remove", help=ReactCog.always_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_always_remove(self, ctx: commands.Context, member: discord.Member):
        await super().always_remove(ctx, member)
        pass

    @hello.group(name="triggers")
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_triggers(self, ctx: commands.Context):
        """Sets the list of trigger phrases to generate hello messages."""
        pass

    @hello_triggers.command(name="list", help=ReactCog.trigger_list.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_triggers_list(self, ctx: commands.Context):
        await super().trigger_list(ctx)
        pass

    @hello_triggers.command(name="add", help=ReactCog.trigger_add.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_triggers_add(self, ctx: commands.Context, *, phrase: str):
        await super().trigger_add(ctx, phrase=phrase)
        pass

    @hello_triggers.command(name="remove", help=ReactCog.trigger_remove.__doc__)
    @commands.has_guild_permissions(manage_roles=True)
    async def hello_triggers_remove(
        self, ctx: commands.Context, *, phrase: PhraseOrIndex
    ):
        await super().trigger_remove(ctx, phrase=phrase)
        pass
